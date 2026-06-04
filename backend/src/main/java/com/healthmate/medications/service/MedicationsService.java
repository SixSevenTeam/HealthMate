package com.healthmate.medications.service;

import com.healthmate.aigateway.service.AIGatewayService;
import com.healthmate.medications.entity.*;
import com.healthmate.medications.repository.*;
import com.healthmate.exception.ResourceNotFoundException;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.io.Resource;
import org.springframework.core.io.UrlResource;
import org.springframework.dao.DataIntegrityViolationException;
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
import java.time.ZonedDateTime;
import java.util.ArrayList;
import java.util.List;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
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
    private final AIGatewayService aiGatewayService;

    @Value("${healthmate.dataset-root:dataset/healthmate_2018-2023/data}")
    private String datasetRoot;

    public MedicationsService(DrugRepository drugRepository, 
                              UserMedicationRepository userMedicationRepository,
                              ScheduleRepository scheduleRepository,
                              IntakeLogRepository intakeLogRepository,
                              AIGatewayService aiGatewayService) {
        this.drugRepository = drugRepository;
        this.userMedicationRepository = userMedicationRepository;
        this.scheduleRepository = scheduleRepository;
        this.intakeLogRepository = intakeLogRepository;
        this.aiGatewayService = aiGatewayService;
    }

    public List<Drug> searchDrugs(String query) {
        return drugRepository.searchByQuery(query);
    }

    public List<com.healthmate.medications.dto.DrugMappingResponse> getAllDrugMappings() {
        List<Drug> all = drugRepository.findAll();
        Pattern p = Pattern.compile("(doc_\\d+\\.htm)", Pattern.CASE_INSENSITIVE);
        return all.stream()
            .map(d -> {
                String source = d.getSourceFile();
                if (source == null || source.isBlank()) {
                    String details = d.getDetailsHtmlPath();
                    if (details != null && !details.isBlank()) {
                        Matcher m = p.matcher(details);
                        if (m.find()) {
                            source = m.group(1);
                        } else {
                            try {
                                source = Paths.get(details).getFileName().toString();
                            } catch (Exception ex) {
                                source = details;
                            }
                        }
                    }
                }

                return com.healthmate.medications.dto.DrugMappingResponse.builder()
                    .id(d.getId())
                    .sourceFile(source)
                    .detailsHtmlPath(d.getDetailsHtmlPath())
                    .build();
            })
            .toList();
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
        invalidateTipsCache(userId, "medication_added");
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
        invalidateTipsCache(userId, "medication_created");
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
        invalidateTipsCache(userId, "schedule_added");
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
        invalidateTipsCache(userId, "schedule_deleted");
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
    public int markOverduePendingIntakeLogs() {
        ZoneId zone = ZoneId.systemDefault();
        Instant startOfToday = ZonedDateTime.now(zone)
            .toLocalDate()
            .atStartOfDay(zone)
            .toInstant();

        List<IntakeLog> overdueLogs = intakeLogRepository.findByStatusAndScheduledAtLessThan("pending", startOfToday);
        if (overdueLogs.isEmpty()) {
            return 0;
        }

        for (IntakeLog log : overdueLogs) {
            log.setStatus("missed");
            log.setTakenAt(null);
            log.setConfirmedVia("system");
        }

        intakeLogRepository.saveAll(overdueLogs);
        log.info("Marked overdue intake logs as missed: {}", overdueLogs.size());
        return overdueLogs.size();
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
            // takenAt should reflect the scheduled time; markedAt stores moment of user action
            intakeLog.setTakenAt(intakeLog.getScheduledAt());
            intakeLog.setMarkedAt(Instant.now());
        } else {
            intakeLog.setTakenAt(null);
            intakeLog.setMarkedAt(Instant.now());
        }
        intakeLog.setConfirmedVia("app");
        IntakeLog updated = intakeLogRepository.save(intakeLog);
        invalidateTipsCache(userId, "intake_status_" + normalizedStatus);
        log.info("Intake status updated: {} -> {}", logId, normalizedStatus);
        return updated;
    }

    @Transactional
    public IntakeLog markIntake(UUID userMedicationId, UUID scheduleId, LocalDate date, UUID userId, String status) {
        UserMedication medication = getUserMedication(userMedicationId, userId);
        Schedule schedule = scheduleRepository.findById(scheduleId)
            .orElseThrow(() -> new ResourceNotFoundException("Schedule not found"));

        if (!userMedicationId.equals(schedule.getUserMedicationId())) {
            throw new ResourceNotFoundException("Schedule not found");
        }

        String normalizedStatus = status == null ? "" : status.trim().toLowerCase();
        if (!ALLOWED_MANUAL_STATUSES.contains(normalizedStatus)) {
            throw new IllegalArgumentException("Allowed statuses: taken, missed, skipped");
        }

        ZoneId zone = ZoneId.systemDefault();
        Instant scheduledAt = date.atTime(schedule.getTimeOfDay()).atZone(zone).toInstant();

        IntakeLog intakeLog = intakeLogRepository.findFirstByUserMedicationIdAndScheduledAtOrderByCreatedAtDesc(userMedicationId, scheduledAt)
            .orElseGet(() -> IntakeLog.builder()
                .userMedicationId(medication.getId())
                .scheduledAt(scheduledAt)
                .build());

        intakeLog.setStatus(normalizedStatus);
        if ("taken".equals(normalizedStatus)) {
            // When user marks intake for a specific date, record takenAt as scheduledAt
            intakeLog.setTakenAt(scheduledAt);
            intakeLog.setMarkedAt(Instant.now());
        } else {
            intakeLog.setTakenAt(null);
            intakeLog.setMarkedAt(Instant.now());
        }
        intakeLog.setConfirmedVia("app");

        try {
            IntakeLog updated = intakeLogRepository.save(intakeLog);
            invalidateTipsCache(userId, "intake_marked_" + normalizedStatus);
            log.info("Intake marked: medication={} schedule={} date={} status={}", userMedicationId, scheduleId, date, normalizedStatus);
            return updated;
        } catch (DataIntegrityViolationException ex) {
            // Handle races/constraint conflicts by reloading latest row and applying status update.
            IntakeLog existing = intakeLogRepository
                .findFirstByUserMedicationIdAndScheduledAtOrderByCreatedAtDesc(userMedicationId, scheduledAt)
                .orElseThrow(() -> ex);

            existing.setStatus(normalizedStatus);
            if ("taken".equals(normalizedStatus)) {
                existing.setTakenAt(scheduledAt);
                existing.setMarkedAt(Instant.now());
            } else {
                existing.setTakenAt(null);
                existing.setMarkedAt(Instant.now());
            }
            existing.setConfirmedVia("app");

            IntakeLog updated = intakeLogRepository.save(existing);
            invalidateTipsCache(userId, "intake_marked_" + normalizedStatus);
            log.warn(
                "Intake mark conflict resolved by retry: medication={} schedule={} date={} status={}",
                userMedicationId,
                scheduleId,
                date,
                normalizedStatus
            );
            return updated;
        }
    }

    @Transactional
    public void deactivateUserMedication(UUID id, UUID userId) {
        UserMedication medication = userMedicationRepository.findByIdAndUserId(id, userId)
            .orElseThrow(() -> new ResourceNotFoundException("Medication not found"));
        
        medication.setIsActive(false);
        userMedicationRepository.save(medication);
        // Remove future pending logs — deactivation affects only future expected doses
        intakeLogRepository.deleteByUserMedicationIdAndStatusAndScheduledAtGreaterThan(
            id,
            "pending",
            Instant.now()
        );
        invalidateTipsCache(userId, "medication_deactivated");
        log.info("Medication deactivated and future pending logs removed: {}", id);
    }

    @Transactional
    public UserMedication setMedicationActive(UUID id, UUID userId, boolean isActive) {
        UserMedication medication = getUserMedication(id, userId);
        medication.setIsActive(isActive);
        UserMedication saved = userMedicationRepository.save(medication);
        log.info("Medication active status changed: {} -> {}", id, isActive);
        if (Boolean.TRUE.equals(isActive)) {
            // When activating, regenerate future pending logs according to schedules and medication dates
            regenerateFuturePendingLogs(id);
        } else {
            // When deactivating via this method, remove future pending logs
            intakeLogRepository.deleteByUserMedicationIdAndStatusAndScheduledAtGreaterThan(
                id,
                "pending",
                Instant.now()
            );
        }
        invalidateTipsCache(userId, "medication_active_changed");
        return saved;
    }

    private void invalidateTipsCache(UUID userId, String reason) {
        aiGatewayService.invalidateTipsCache(userId, reason);
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
            candidates.add(root.resolve(raw).normalize());
            candidates.add(cwd.resolve(raw).normalize());
            candidates.add(cwd.resolve("..").resolve(raw).normalize());
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

    public record DrugImagePayload(Resource image, String contentType) {
    }
}
