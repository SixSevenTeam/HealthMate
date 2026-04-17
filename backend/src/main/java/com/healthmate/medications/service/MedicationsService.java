package com.healthmate.medications.service;

import com.healthmate.medications.entity.*;
import com.healthmate.medications.repository.*;
import com.healthmate.exception.ResourceNotFoundException;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.time.Instant;
import java.time.LocalDate;
import java.time.ZoneId;
import java.util.ArrayList;
import java.util.List;
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
}
