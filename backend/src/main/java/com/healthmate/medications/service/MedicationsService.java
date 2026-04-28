package com.healthmate.medications.service;

import com.healthmate.medications.entity.*;
import com.healthmate.medications.repository.*;
import com.healthmate.exception.ResourceNotFoundException;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.io.Resource;
import org.springframework.core.io.UrlResource;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.io.IOException;
import java.math.BigDecimal;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.time.Instant;
import java.time.LocalDate;
import java.time.ZoneId;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.Set;
import java.util.UUID;

import com.healthmate.profile.service.UserContextDTO;

@Slf4j
@Service
public class MedicationsService {

    private static final Set<String> ALLOWED_MANUAL_STATUSES = Set.of("taken", "missed", "skipped");

    private final DrugRepository drugRepository;
    private final UserMedicationRepository userMedicationRepository;
    private final ScheduleRepository scheduleRepository;
    private final IntakeLogRepository intakeLogRepository;

    @Value("${healthmate.dataset-root:dataset/healthmate_2018-2023/data}")
    private String datasetRoot;

    public MedicationsService(DrugRepository drugRepository, 
                              UserMedicationRepository userMedicationRepository,
                              ScheduleRepository scheduleRepository,
                              IntakeLogRepository intakeLogRepository) {
        this.drugRepository = drugRepository;
        this.userMedicationRepository = userMedicationRepository;
        this.scheduleRepository = scheduleRepository;
        this.intakeLogRepository = intakeLogRepository;
    }

    public List<Drug> searchDrugs(String query) {
        return drugRepository.searchByQuery(query);
    }

    public Drug getDrugById(UUID drugId) {
        return drugRepository.findById(drugId)
            .orElseThrow(() -> new ResourceNotFoundException("Drug not found"));
    }

    public String getDrugDetailsHtml(UUID drugId) {
        Drug drug = getDrugById(drugId);

        if (drug.getDetailsHtmlPath() != null && !drug.getDetailsHtmlPath().isBlank()) {
            try {
                Path detailsPath = resolveStoredPath(drug.getDetailsHtmlPath());
                if (Files.exists(detailsPath) && Files.isRegularFile(detailsPath)) {
                    return readHtmlWithFallback(detailsPath);
                }
            } catch (ResourceNotFoundException ex) {
                log.debug("Drug details path is outside dataset root or invalid: {}", drug.getDetailsHtmlPath());
            }
        }

        throw new ResourceNotFoundException("Drug details HTML not found");
    }

    public DrugImagePayload getDrugPackImagePayload(UUID drugId) {
        Drug drug = getDrugById(drugId);
        if (drug.getPackImagePath() == null || drug.getPackImagePath().isBlank()) {
            throw new ResourceNotFoundException("Drug image not found");
        }

        Path imagePath = resolveStoredPath(drug.getPackImagePath());
        if (!Files.exists(imagePath) || !Files.isRegularFile(imagePath)) {
            throw new ResourceNotFoundException("Drug image not found");
        }

        Resource image;
        try {
            image = new UrlResource(imagePath.toUri());
        } catch (Exception ex) {
            throw new IllegalStateException("Failed to read drug image", ex);
        }

        return new DrugImagePayload(image, detectImageContentType(imagePath));
    }

    public Resource getDrugPackImage(UUID drugId) {
        return getDrugPackImagePayload(drugId).image();
    }

    public String resolveContentTypeForImage(UUID drugId) {
        return getDrugPackImagePayload(drugId).contentType();
    }

    private String detectImageContentType(Path imagePath) {
        String probed = null;
        try {
            probed = Files.probeContentType(imagePath);
        } catch (IOException ex) {
            log.debug("Could not probe content type for {}", imagePath, ex);
        }

        if (probed != null && !probed.isBlank()) {
            return probed;
        }

        String lowerPath = imagePath.toString().toLowerCase(Locale.ROOT);
        if (lowerPath.endsWith(".png")) {
            return "image/png";
        }
        if (lowerPath.endsWith(".webp")) {
            return "image/webp";
        }
        if (lowerPath.endsWith(".gif")) {
            return "image/gif";
        }
        return "image/jpeg";
    }

    public Page<UserMedication> getUserMedications(UUID userId, Pageable pageable) {
        return userMedicationRepository.findByUserId(userId, pageable);
    }

    public UserMedication getUserMedication(UUID id, UUID userId) {
        return userMedicationRepository.findByIdAndUserId(id, userId)
            .orElseThrow(() -> new ResourceNotFoundException("Medication not found"));
    }

    @Transactional
    public UserMedication addUserMedication(UUID userId, UserMedication medication) {
        medication.setUserId(userId);
        UserMedication saved = userMedicationRepository.save(medication);
        log.info("User medication added: {}", saved.getId());
        return saved;
    }

    @Transactional
    public UserMedication createMedicationWithSchedules(UUID userId, UserMedication medication, List<Schedule> schedules) {
        if (schedules == null || schedules.isEmpty()) {
            throw new IllegalArgumentException("At least one schedule is required");
        }
        if (medication.getDrugId() == null && (medication.getCustomName() == null || medication.getCustomName().isBlank())) {
            throw new IllegalArgumentException("Either drugId or customName must be provided");
        }

        medication.setUserId(userId);
        UserMedication savedMedication = userMedicationRepository.save(medication);

        for (Schedule schedule : schedules) {
            schedule.setUserMedicationId(savedMedication.getId());
            scheduleRepository.save(schedule);
        }

        regenerateFuturePendingLogs(savedMedication.getId());
        log.info("User medication created with schedules: {}", savedMedication.getId());
        return savedMedication;
    }

    public List<Schedule> getSchedules(UUID userMedicationId, UUID userId) {
        getUserMedication(userMedicationId, userId);
        return scheduleRepository.findByUserMedicationId(userMedicationId);
    }

    @Transactional
    public Schedule addSchedule(UUID userMedicationId, UUID userId, Schedule schedule) {
        getUserMedication(userMedicationId, userId);
        schedule.setUserMedicationId(userMedicationId);
        Schedule saved = scheduleRepository.save(schedule);
        regenerateFuturePendingLogs(userMedicationId);
        log.info("Schedule added for medication: {}", userMedicationId);
        return saved;
    }

    @Transactional
    public void deleteSchedule(UUID scheduleId, UUID userId) {
        Schedule schedule = scheduleRepository.findById(scheduleId)
            .orElseThrow(() -> new ResourceNotFoundException("Schedule not found"));

        getUserMedication(schedule.getUserMedicationId(), userId);
        scheduleRepository.delete(schedule);
        regenerateFuturePendingLogs(schedule.getUserMedicationId());
        log.info("Schedule deleted: {}", scheduleId);
    }

    public List<IntakeLog> getIntakeLogs(UUID userMedicationId, UUID userId, Instant from, Instant to) {
        getUserMedication(userMedicationId, userId);
        return intakeLogRepository.findByUserMedicationIdAndScheduledAtBetween(userMedicationId, from, to);
    }

    @Transactional
    public void confirmIntake(UUID logId, UUID userId) {
        setIntakeStatus(logId, userId, "taken");
    }

    @Transactional
    public IntakeLog setIntakeStatus(UUID logId, UUID userId, String status) {
        IntakeLog intakeLog = intakeLogRepository.findById(logId)
            .orElseThrow(() -> new ResourceNotFoundException("Intake log not found"));

        getUserMedication(intakeLog.getUserMedicationId(), userId);

        String normalizedStatus = status == null ? "" : status.trim().toLowerCase();
        if (!ALLOWED_MANUAL_STATUSES.contains(normalizedStatus)) {
            throw new IllegalArgumentException("Allowed statuses: taken, missed, skipped");
        }

        intakeLog.setStatus(normalizedStatus);
        if ("taken".equals(normalizedStatus)) {
            intakeLog.setTakenAt(Instant.now());
        } else {
            intakeLog.setTakenAt(null);
        }
        intakeLog.setConfirmedVia("app");
        IntakeLog updated = intakeLogRepository.save(intakeLog);
        log.info("Intake status updated: {} -> {}", logId, normalizedStatus);
        return updated;
    }

    @Transactional
    public void deactivateUserMedication(UUID id, UUID userId) {
        UserMedication medication = userMedicationRepository.findByIdAndUserId(id, userId)
            .orElseThrow(() -> new ResourceNotFoundException("Medication not found"));
        
        medication.setIsActive(false);
        userMedicationRepository.save(medication);
        log.info("Medication deactivated: {}", id);
    }

    @Transactional
    public UserMedication setMedicationActive(UUID id, UUID userId, boolean isActive) {
        UserMedication medication = getUserMedication(id, userId);
        medication.setIsActive(isActive);
        UserMedication saved = userMedicationRepository.save(medication);
        log.info("Medication active status changed: {} -> {}", id, isActive);
        return saved;
    }

    public String resolveTradeName(UserMedication medication) {
        if (medication.getDrugId() != null) {
            return drugRepository.findById(medication.getDrugId())
                .map(Drug::getTradeName)
                .orElse(medication.getCustomName());
        }
        return medication.getCustomName();
    }

    public String resolveInternationalName(UserMedication medication) {
        if (medication.getDrugId() == null) {
            return null;
        }
        return drugRepository.findById(medication.getDrugId())
            .map(Drug::getInternationalName)
            .orElse(null);
    }

    public String calculateDoseWarning(UserMedication medication) {
        if (medication.getDrugId() == null || medication.getDoseAmount() == null) {
            return null;
        }

        Drug drug = drugRepository.findById(medication.getDrugId()).orElse(null);
        if (drug == null) {
            return null;
        }

        BigDecimal min = drug.getMinDose();
        BigDecimal max = drug.getMaxDose();
        BigDecimal actual = medication.getDoseAmount();

        if (min != null && actual.compareTo(min) < 0) {
            return "Dose is below minimum recommended";
        }
        if (max != null && actual.compareTo(max) > 0) {
            return "Dose is above maximum recommended";
        }

        return null;
    }

    public List<UserContextDTO.ActiveMedicationDTO> getActiveMedicationsForContext(UUID userId) {
        List<UserMedication> active = userMedicationRepository.findByUserIdAndIsActive(userId, true);
        List<UserContextDTO.ActiveMedicationDTO> result = new ArrayList<>();

        for (UserMedication medication : active) {
            String tradeName = medication.getCustomName();
            String internationalName = null;

            if (medication.getDrugId() != null) {
                var drugOpt = drugRepository.findById(medication.getDrugId());
                if (drugOpt.isPresent()) {
                    tradeName = drugOpt.get().getTradeName();
                    internationalName = drugOpt.get().getInternationalName();
                }
            }

            result.add(new UserContextDTO.ActiveMedicationDTO(
                tradeName,
                internationalName,
                medication.getDoseAmount(),
                medication.getDoseUnit(),
                medication.getInstructions()
            ));
        }

        return result;
    }

    private void generateIntakeLogs(UUID userMedicationId) {
        UserMedication medication = userMedicationRepository.findById(userMedicationId)
            .orElseThrow(() -> new ResourceNotFoundException("Medication not found"));
        List<Schedule> schedules = scheduleRepository.findByUserMedicationId(userMedicationId);

        ZoneId zone = ZoneId.systemDefault();
        Instant now = Instant.now();

        LocalDate today = LocalDate.now(zone);
        LocalDate startDate = today;
        if (medication.getStartDate() != null && medication.getStartDate().isAfter(startDate)) {
            startDate = medication.getStartDate();
        }

        LocalDate endDate = startDate.plusDays(30);
        if (medication.getEndDate() != null && medication.getEndDate().isBefore(endDate)) {
            endDate = medication.getEndDate();
        }

        if (endDate.isBefore(startDate)) {
            return;
        }
        
        for (LocalDate date = startDate; !date.isAfter(endDate); date = date.plusDays(1)) {
            int dayOfWeek = date.getDayOfWeek().getValue();

            for (Schedule schedule : schedules) {
                boolean isScheduledDay = false;
                for (Integer day : schedule.getDaysOfWeek()) {
                    if (day.equals(dayOfWeek)) {
                        isScheduledDay = true;
                        break;
                    }
                }
                
                if (isScheduledDay) {
                    Instant scheduledAt = date.atTime(schedule.getTimeOfDay())
                                        .atZone(zone)
                        .toInstant();

                                    if (!scheduledAt.isAfter(now)) {
                                        continue;
                                    }

                    IntakeLog log = IntakeLog.builder()
                        .userMedicationId(userMedicationId)
                        .scheduledAt(scheduledAt)
                        .status("pending")
                        .build();

                    intakeLogRepository.save(log);
                }
            }
        }
    }

                    private void regenerateFuturePendingLogs(UUID userMedicationId) {
                        intakeLogRepository.deleteByUserMedicationIdAndStatusAndScheduledAtGreaterThan(
                            userMedicationId,
                            "pending",
                            Instant.now()
                        );
                        generateIntakeLogs(userMedicationId);
                    }

    private String readHtmlWithFallback(Path path) {
        try {
            byte[] bytes = Files.readAllBytes(path);
            String utf8 = new String(bytes, StandardCharsets.UTF_8);
            if (!utf8.contains("\uFFFD")) {
                return utf8;
            }
            return new String(bytes, java.nio.charset.Charset.forName("windows-1251"));
        } catch (IOException ex) {
            throw new IllegalStateException("Failed to read drug details HTML", ex);
        }
    }

    private Path resolveStoredPath(String storedPath) {
        if (storedPath == null || storedPath.isBlank()) {
            throw new ResourceNotFoundException("Drug file not found");
        }

        Path root = Paths.get(datasetRoot).toAbsolutePath().normalize();
        Path raw = Paths.get(storedPath).normalize();
        Path cwd = Paths.get("").toAbsolutePath().normalize();

        List<Path> candidates = new ArrayList<>();
        if (raw.isAbsolute()) {
            candidates.add(raw.toAbsolutePath().normalize());
        } else {
            candidates.add(cwd.resolve(raw).normalize());

            Path current = cwd.getParent();
            while (current != null) {
                candidates.add(current.resolve(raw).normalize());
                current = current.getParent();
            }

            candidates.add(resolveRelativeToDatasetRoot(root, raw));
            candidates.add(root.resolve(raw).normalize());
        }

        Path firstSafe = null;
        for (Path candidate : candidates) {
            if (!candidate.startsWith(root)) {
                continue;
            }

            if (firstSafe == null) {
                firstSafe = candidate;
            }

            if (Files.exists(candidate)) {
                return candidate;
            }
        }

        if (firstSafe != null) {
            return firstSafe;
        }

        throw new ResourceNotFoundException("Drug file not found");
    }

    private Path resolveRelativeToDatasetRoot(Path root, Path storedPath) {
        List<String> rootSegments = toSegments(root);
        List<String> storedSegments = toSegments(storedPath);

        for (int overlap = Math.min(rootSegments.size(), storedSegments.size()); overlap > 0; overlap--) {
            List<String> rootSuffix = rootSegments.subList(rootSegments.size() - overlap, rootSegments.size());
            List<String> storedPrefix = storedSegments.subList(0, overlap);
            if (!rootSuffix.equals(storedPrefix)) {
                continue;
            }

            Path remainder = segmentsToPath(storedSegments.subList(overlap, storedSegments.size()));
            return root.resolve(remainder).normalize();
        }

        return root.resolve(storedPath).normalize();
    }

    private List<String> toSegments(Path path) {
        List<String> segments = new ArrayList<>();
        for (Path segment : path) {
            segments.add(segment.toString());
        }
        return segments;
    }

    private Path segmentsToPath(List<String> segments) {
        if (segments.isEmpty()) {
            return Paths.get("");
        }

        Path result = Paths.get(segments.get(0));
        for (int index = 1; index < segments.size(); index++) {
            result = result.resolve(segments.get(index));
        }
        return result;
    }

    public record DrugImagePayload(Resource image, String contentType) {
    }
}
