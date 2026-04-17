package com.healthmate.dashboard.service;

import com.healthmate.medications.entity.Drug;
import com.healthmate.medications.entity.IntakeLog;
import com.healthmate.medications.entity.UserMedication;
import com.healthmate.medications.repository.DrugRepository;
import com.healthmate.medications.repository.IntakeLogRepository;
import com.healthmate.medications.repository.UserMedicationRepository;
import org.springframework.stereotype.Service;

import java.time.Instant;
import java.time.LocalDate;
import java.time.ZoneId;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.UUID;
import java.util.stream.Collectors;

@Service
public class DashboardService {

    private final IntakeLogRepository intakeLogRepository;
    private final UserMedicationRepository userMedicationRepository;
    private final DrugRepository drugRepository;

    public DashboardService(
        IntakeLogRepository intakeLogRepository,
        UserMedicationRepository userMedicationRepository,
        DrugRepository drugRepository
    ) {
        this.intakeLogRepository = intakeLogRepository;
        this.userMedicationRepository = userMedicationRepository;
        this.drugRepository = drugRepository;
    }

    public DashboardSummaryResponse getSummary(UUID userId, LocalDate from, LocalDate to) {
        if (from == null || to == null) {
            throw new IllegalArgumentException("Both 'from' and 'to' are required");
        }
        if (to.isBefore(from)) {
            throw new IllegalArgumentException("'to' date must be greater than or equal to 'from' date");
        }

        ZoneId zone = ZoneId.systemDefault();
        Instant fromInstant = from.atStartOfDay(zone).toInstant();
        Instant toInstant = to.atStartOfDay(zone).plusDays(1).toInstant();

        List<UserMedication> userMedications = userMedicationRepository.findByUserIdAndIsActive(userId, true);
        if (userMedications.isEmpty()) {
            return DashboardSummaryResponse.builder()
                .period(new DashboardSummaryResponse.PeriodDTO(from, to))
                .adherence(List.of())
                .insights(List.of("No active medications for selected period."))
                .build();
        }

        List<UUID> medicationIds = userMedications.stream()
            .map(UserMedication::getId)
            .toList();

        List<IntakeLog> logs = intakeLogRepository.findByUserMedicationIdInAndScheduledAtGreaterThanEqualAndScheduledAtLessThan(
            medicationIds,
            fromInstant,
            toInstant
        );

        Map<UUID, List<IntakeLog>> logsByMedication = logs.stream()
            .collect(Collectors.groupingBy(IntakeLog::getUserMedicationId));

        Map<UUID, Drug> drugsById = drugRepository.findAllById(
                userMedications.stream()
                    .map(UserMedication::getDrugId)
                    .filter(Objects::nonNull)
                    .toList()
            )
            .stream()
            .collect(Collectors.toMap(Drug::getId, d -> d, (left, right) -> left, LinkedHashMap::new));

        List<DashboardSummaryResponse.AdherenceDTO> adherence = new ArrayList<>();
        for (UserMedication medication : userMedications) {
            List<IntakeLog> medicationLogs = logsByMedication.getOrDefault(medication.getId(), List.of());

            int totalScheduled = medicationLogs.size();
            int totalTaken = (int) medicationLogs.stream().filter(this::isTaken).count();
            double adherencePercent = totalScheduled == 0
                ? 0.0
                : round2(totalTaken * 100.0 / totalScheduled);

            List<String> missedDates = medicationLogs.stream()
                .filter(log -> !isTaken(log))
                .map(log -> LocalDate.ofInstant(log.getScheduledAt(), zone).toString())
                .distinct()
                .sorted()
                .toList();

            adherence.add(new DashboardSummaryResponse.AdherenceDTO(
                medication.getId().toString(),
                resolveTradeName(medication, drugsById),
                totalScheduled,
                totalTaken,
                adherencePercent,
                missedDates
            ));
        }

        adherence.sort(Comparator.comparing(DashboardSummaryResponse.AdherenceDTO::getTradeName, String.CASE_INSENSITIVE_ORDER));

        List<String> insights = buildInsights(adherence);

        return DashboardSummaryResponse.builder()
            .period(new DashboardSummaryResponse.PeriodDTO(from, to))
            .adherence(adherence)
            .insights(insights)
            .build();
    }

    private boolean isTaken(IntakeLog log) {
        return "taken".equalsIgnoreCase(log.getStatus()) && log.getTakenAt() != null;
    }

    private String resolveTradeName(UserMedication medication, Map<UUID, Drug> drugsById) {
        if (medication.getCustomName() != null && !medication.getCustomName().isBlank()) {
            return medication.getCustomName();
        }
        if (medication.getDrugId() != null && drugsById.containsKey(medication.getDrugId())) {
            return drugsById.get(medication.getDrugId()).getTradeName();
        }
        return "Medication " + medication.getId().toString().substring(0, 8);
    }

    private List<String> buildInsights(List<DashboardSummaryResponse.AdherenceDTO> adherence) {
        if (adherence.isEmpty()) {
            return List.of("No adherence data for selected period.");
        }

        int totalScheduled = adherence.stream().mapToInt(DashboardSummaryResponse.AdherenceDTO::getTotalScheduled).sum();
        int totalTaken = adherence.stream().mapToInt(DashboardSummaryResponse.AdherenceDTO::getTotalTaken).sum();
        double overall = totalScheduled == 0 ? 0.0 : round2(totalTaken * 100.0 / totalScheduled);

        List<String> insights = new ArrayList<>();
        insights.add("Overall adherence: " + overall + "%");

        if (overall >= 90) {
            insights.add("Adherence is excellent in the selected period.");
        } else if (overall >= 75) {
            insights.add("Adherence is good, but there is room for improvement.");
        } else if (overall >= 50) {
            insights.add("Adherence is moderate. Consider reminders for missed intakes.");
        } else {
            insights.add("Adherence is low. A stricter routine may be needed.");
        }

        long lowAdherenceCount = adherence.stream()
            .filter(item -> item.getAdherencePercent() < 80.0)
            .count();
        if (lowAdherenceCount == 0) {
            insights.add("All medications are within the 80% adherence target.");
        } else {
            insights.add(lowAdherenceCount + " medication(s) are below the 80% adherence target.");
        }

        long medicationsWithMissed = adherence.stream()
            .filter(item -> !item.getMissedDates().isEmpty())
            .count();
        if (medicationsWithMissed > 0) {
            insights.add(medicationsWithMissed + " medication(s) have missed intake dates.");
        }

        return insights;
    }

    private double round2(double value) {
        return Math.round(value * 100.0) / 100.0;
    }
}
