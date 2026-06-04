package com.healthmate.dashboard.service;

import com.healthmate.aigateway.dto.AiTipsRequest;
import com.healthmate.aigateway.dto.AiTipsResponse;
import com.healthmate.aigateway.service.AIGatewayService;
import com.healthmate.medications.entity.Drug;
import com.healthmate.medications.entity.IntakeLog;
import com.healthmate.medications.entity.Schedule;
import com.healthmate.medications.entity.UserMedication;
import com.healthmate.medications.repository.DrugRepository;
import com.healthmate.medications.repository.IntakeLogRepository;
import com.healthmate.medications.repository.ScheduleRepository;
import com.healthmate.medications.repository.UserMedicationRepository;
import com.healthmate.medications.service.MedicationsService;
import com.healthmate.profile.service.ProfileService;
import com.healthmate.profile.service.UserContextDTO;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.domain.Pageable;
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
import java.util.function.Function;
import java.util.stream.Collectors;

@Slf4j
@Service
public class DashboardService {

    private final IntakeLogRepository intakeLogRepository;
    private final UserMedicationRepository userMedicationRepository;
    private final ScheduleRepository scheduleRepository;
    private final DrugRepository drugRepository;
    private final ProfileService profileService;
    private final MedicationsService medicationsService;
    private final AIGatewayService aiGatewayService;

    public DashboardService(
        IntakeLogRepository intakeLogRepository,
        UserMedicationRepository userMedicationRepository,
        ScheduleRepository scheduleRepository,
        DrugRepository drugRepository,
        ProfileService profileService,
        MedicationsService medicationsService,
        AIGatewayService aiGatewayService
    ) {
        this.intakeLogRepository = intakeLogRepository;
        this.userMedicationRepository = userMedicationRepository;
        this.scheduleRepository = scheduleRepository;
        this.drugRepository = drugRepository;
        this.profileService = profileService;
        this.medicationsService = medicationsService;
        this.aiGatewayService = aiGatewayService;
    }

    public DashboardSummaryResponse getSummary(UUID userId, LocalDate from, LocalDate to, String scope) {
        if (from == null || to == null) {
            throw new IllegalArgumentException("Both 'from' and 'to' are required");
        }
        if (to.isBefore(from)) {
            throw new IllegalArgumentException("'to' date must be greater than or equal to 'from' date");
        }

        String normalizedScope = normalizeScope(scope);

        ZoneId zone = ZoneId.systemDefault();
        Instant fromInstant = from.atStartOfDay(zone).toInstant();
        Instant toInstant = to.atStartOfDay(zone).plusDays(1).toInstant();
        Instant now = Instant.now();

        List<UserMedication> allUserMedications = userMedicationRepository.findByUserId(userId, Pageable.unpaged()).getContent();
        List<UserMedication> userMedications = allUserMedications.stream()
            .filter(medication -> matchesScope(medication, normalizedScope))
            .toList();

        if (userMedications.isEmpty()) {
            List<String> fallbackRecommendations = defaultGeneralRecommendations();
            return DashboardSummaryResponse.builder()
                .period(new DashboardSummaryResponse.PeriodDTO(from, to))
                .adherence(List.of())
                .dailySeries(buildEmptyDailySeries(from, to))
                .insights(List.of("Для выбранного фильтра пока нет лекарств в отчете."))
                .recommendations(fallbackRecommendations)
                .build();
        }

        List<UUID> medicationIds = userMedications.stream()
            .map(UserMedication::getId)
            .toList();

        Map<UUID, List<Schedule>> schedulesByMedication = userMedications.stream()
            .collect(Collectors.toMap(
                UserMedication::getId,
                medication -> scheduleRepository.findByUserMedicationId(medication.getId()),
                (left, right) -> left,
                LinkedHashMap::new
            ));

        boolean hasAnySchedule = schedulesByMedication.values().stream().anyMatch(list -> list != null && !list.isEmpty());

        List<IntakeLog> logs = intakeLogRepository.findByUserMedicationIdInAndScheduledAtGreaterThanEqualAndScheduledAtLessThan(
            medicationIds,
            fromInstant,
            toInstant
        );

        if (!hasAnySchedule && !logs.isEmpty()) {
            return buildSummaryFromLogsOnly(userId, userMedications, logs, from, to, normalizedScope, now, zone);
        }

        Map<UUID, Map<Instant, IntakeLog>> logsByMedicationAndInstant = logs.stream()
            .collect(Collectors.groupingBy(
                IntakeLog::getUserMedicationId,
                LinkedHashMap::new,
                Collectors.toMap(
                    IntakeLog::getScheduledAt,
                    Function.identity(),
                    (left, right) -> left,
                    LinkedHashMap::new
                )
            ));

        Map<UUID, MedicationStats> medicationStats = new LinkedHashMap<>();
        for (UserMedication medication : userMedications) {
            medicationStats.put(medication.getId(), new MedicationStats());
        }

        List<DashboardSummaryResponse.DailySeriesDTO> dailySeries = new ArrayList<>();
        for (LocalDate day = from; !day.isAfter(to); day = day.plusDays(1)) {
            DailyStats dailyStats = new DailyStats();

            for (UserMedication medication : userMedications) {
                MedicationStats stats = medicationStats.get(medication.getId());
                List<Schedule> schedules = schedulesByMedication.getOrDefault(medication.getId(), List.of());

                for (Schedule schedule : schedules) {
                    if (!isScheduledDay(day, schedule.getDaysOfWeek())) {
                        continue;
                    }

                    Instant scheduledAt = day.atTime(schedule.getTimeOfDay()).atZone(zone).toInstant();
                    if (scheduledAt.isBefore(fromInstant) || !scheduledAt.isBefore(toInstant)) {
                        continue;
                    }

                    // Respect medication start/end dates: do not count schedules outside the active range
                    if (medication.getStartDate() != null && day.isBefore(medication.getStartDate())) {
                        continue;
                    }
                    if (medication.getEndDate() != null && day.isAfter(medication.getEndDate())) {
                        continue;
                    }

                    // Do not count future expected doses for inactive medications
                    if (!Boolean.TRUE.equals(medication.getIsActive()) && scheduledAt.isAfter(now)) {
                        continue;
                    }

                    stats.totalScheduled++;
                    dailyStats.totalScheduled++;

                    IntakeLog log = logsByMedicationAndInstant
                        .getOrDefault(medication.getId(), Map.of())
                        .get(scheduledAt);

                    String status = resolveStatus(log, scheduledAt, now);
                    if ("taken".equals(status)) {
                        stats.totalTaken++;
                        dailyStats.taken++;
                    } else if ("waiting".equals(status)) {
                        dailyStats.waiting++;
                    } else {
                        stats.missedDates.add(day.toString());
                        dailyStats.missed++;
                    }
                }
            }

            dailySeries.add(new DashboardSummaryResponse.DailySeriesDTO(
                day,
                dailyStats.taken,
                dailyStats.waiting,
                dailyStats.missed,
                dailyStats.totalScheduled
            ));
        }

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
            MedicationStats stats = medicationStats.get(medication.getId());
            int totalScheduled = stats.totalScheduled;
            int totalTaken = stats.totalTaken;
            double adherencePercent = totalScheduled == 0
                ? 0.0
                : round2(totalTaken * 100.0 / totalScheduled);

            adherence.add(new DashboardSummaryResponse.AdherenceDTO(
                medication.getId().toString(),
                resolveTradeName(medication, drugsById),
                totalScheduled,
                totalTaken,
                adherencePercent,
                stats.missedDates.stream().distinct().sorted().toList()
            ));
        }

        adherence.sort(Comparator.comparing(DashboardSummaryResponse.AdherenceDTO::getTradeName, String.CASE_INSENSITIVE_ORDER));

        TipsBundle tipsBundle = buildTips(userId, from, to, normalizedScope, adherence);

        return DashboardSummaryResponse.builder()
            .period(new DashboardSummaryResponse.PeriodDTO(from, to))
            .adherence(adherence)
            .dailySeries(dailySeries)
            .insights(tipsBundle.insights)
            .recommendations(tipsBundle.recommendations)
            .build();
    }

    private String normalizeScope(String scope) {
        if (scope == null || scope.isBlank()) {
            return "active";
        }

        String normalized = scope.trim().toLowerCase();
        if ("inactive".equals(normalized) || "all".equals(normalized) || "active".equals(normalized)) {
            return normalized;
        }

        return "active";
    }

    private boolean matchesScope(UserMedication medication, String scope) {
        boolean isActive = Boolean.TRUE.equals(medication.getIsActive());
        return switch (scope) {
            case "inactive" -> !isActive;
            case "all" -> true;
            case "active" -> isActive;
            default -> isActive;
        };
    }

    private boolean isScheduledDay(LocalDate date, Integer[] daysOfWeek) {
        if (daysOfWeek == null || daysOfWeek.length == 0) {
            return true;
        }

        int dayOfWeek = date.getDayOfWeek().getValue();
        for (Integer day : daysOfWeek) {
            if (day != null && day == dayOfWeek) {
                return true;
            }
        }

        return false;
    }

    private String resolveStatus(IntakeLog log, Instant scheduledAt, Instant now) {
        if (log != null) {
            String status = log.getStatus() == null ? "" : log.getStatus().trim().toLowerCase();
            if ("taken".equals(status)) {
                return "taken";
            }
            if ("missed".equals(status) || "skipped".equals(status)) {
                return "missed";
            }
        }

        return scheduledAt.isAfter(now) ? "waiting" : "missed";
    }

    private DashboardSummaryResponse buildSummaryFromLogsOnly(
        UUID userId,
        List<UserMedication> userMedications,
        List<IntakeLog> logs,
        LocalDate from,
        LocalDate to,
        String scope,
        Instant now,
        ZoneId zone
    ) {
        Map<UUID, List<IntakeLog>> logsByMedication = logs.stream()
            .collect(Collectors.groupingBy(IntakeLog::getUserMedicationId, LinkedHashMap::new, Collectors.toList()));

        Map<LocalDate, DailyStats> dailyStatsByDate = new LinkedHashMap<>();
        for (LocalDate day = from; !day.isAfter(to); day = day.plusDays(1)) {
            dailyStatsByDate.put(day, new DailyStats());
        }

        Map<UUID, MedicationStats> medicationStats = new LinkedHashMap<>();
        for (UserMedication medication : userMedications) {
            medicationStats.put(medication.getId(), new MedicationStats());
        }

        for (IntakeLog log : logs) {
            LocalDate day = log.getScheduledAt().atZone(zone).toLocalDate();
            DailyStats dailyStats = dailyStatsByDate.get(day);
            if (dailyStats == null) {
                continue;
            }

            MedicationStats stats = medicationStats.get(log.getUserMedicationId());
            if (stats == null) {
                continue;
            }

            String status = resolveStatus(log, log.getScheduledAt(), now);
            dailyStats.totalScheduled++;
            stats.totalScheduled++;

            if ("taken".equals(status)) {
                dailyStats.taken++;
                stats.totalTaken++;
            } else if ("waiting".equals(status)) {
                dailyStats.waiting++;
            } else {
                dailyStats.missed++;
                stats.missedDates.add(day.toString());
            }
        }

        List<DashboardSummaryResponse.DailySeriesDTO> dailySeries = dailyStatsByDate.entrySet().stream()
            .map(entry -> new DashboardSummaryResponse.DailySeriesDTO(
                entry.getKey(),
                entry.getValue().taken,
                entry.getValue().waiting,
                entry.getValue().missed,
                entry.getValue().totalScheduled
            ))
            .toList();

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
            MedicationStats stats = medicationStats.get(medication.getId());
            int totalScheduled = stats.totalScheduled;
            int totalTaken = stats.totalTaken;
            double adherencePercent = totalScheduled == 0
                ? 0.0
                : round2(totalTaken * 100.0 / totalScheduled);

            adherence.add(new DashboardSummaryResponse.AdherenceDTO(
                medication.getId().toString(),
                resolveTradeName(medication, drugsById),
                totalScheduled,
                totalTaken,
                adherencePercent,
                stats.missedDates.stream().distinct().sorted().toList()
            ));
        }

        adherence.sort(Comparator.comparing(DashboardSummaryResponse.AdherenceDTO::getTradeName, String.CASE_INSENSITIVE_ORDER));

        TipsBundle tipsBundle = buildTips(userId, from, to, scope, adherence);

        return DashboardSummaryResponse.builder()
            .period(new DashboardSummaryResponse.PeriodDTO(from, to))
            .adherence(adherence)
            .dailySeries(dailySeries)
            .insights(tipsBundle.insights)
            .recommendations(tipsBundle.recommendations)
            .build();
    }

    private List<DashboardSummaryResponse.DailySeriesDTO> buildEmptyDailySeries(LocalDate from, LocalDate to) {
        List<DashboardSummaryResponse.DailySeriesDTO> series = new ArrayList<>();
        for (LocalDate day = from; !day.isAfter(to); day = day.plusDays(1)) {
            series.add(new DashboardSummaryResponse.DailySeriesDTO(day, 0, 0, 0, 0));
        }
        return series;
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

    private TipsBundle buildTips(
        UUID userId,
        LocalDate from,
        LocalDate to,
        String scope,
        List<DashboardSummaryResponse.AdherenceDTO> adherence
    ) {
        List<String> fallbackInsights = buildRuleBasedInsights(adherence);
        List<String> fallbackRecommendations = buildRuleBasedRecommendations(adherence);

        try {
            log.info("dashboard_tips_generation_started userId={} scope={} period={}-{}", userId, scope, from, to);
            UserContextDTO userContext = profileService.getUserContext(userId);
            userContext.setActiveMedications(medicationsService.getActiveMedicationsForContext(userId));

            int totalScheduled = adherence.stream().mapToInt(DashboardSummaryResponse.AdherenceDTO::getTotalScheduled).sum();
            int totalTaken = adherence.stream().mapToInt(DashboardSummaryResponse.AdherenceDTO::getTotalTaken).sum();
            double overall = totalScheduled == 0 ? 0.0 : round2(totalTaken * 100.0 / totalScheduled);

            List<AiTipsRequest.AdherenceItem> adherenceItems = adherence.stream()
                .map(item -> AiTipsRequest.AdherenceItem.builder()
                    .tradeName(item.getTradeName())
                    .totalScheduled(item.getTotalScheduled())
                    .totalTaken(item.getTotalTaken())
                    .adherencePercent(item.getAdherencePercent())
                    .missedDates(item.getMissedDates())
                    .build())
                .toList();

            AiTipsRequest request = AiTipsRequest.builder()
                .userId(userId)
                .from(from)
                .to(to)
                .scope(scope)
                .userContext(userContext)
                .overallAdherence(overall)
                .totalScheduled(totalScheduled)
                .totalTaken(totalTaken)
                .adherence(adherenceItems)
                .build();

            AiTipsResponse aiTipsResponse = aiGatewayService.generateTips(request);
            log.info("dashboard_tips_generation_result userId={} source={} insights={} recommendations={}", userId, aiTipsResponse.getSource(), aiTipsResponse.safeInsights().size(), aiTipsResponse.safeRecommendations().size());

            List<String> insights = aiTipsResponse.safeInsights();
            List<String> recommendations = aiTipsResponse.safeRecommendations();

            if (insights.isEmpty()) {
                insights = fallbackInsights;
            }
            if (recommendations.isEmpty()) {
                recommendations = fallbackRecommendations;
            }

            return new TipsBundle(insights, recommendations);
        } catch (Exception ex) {
            log.warn("dashboard_tips_generation_fallback userId={} reason={}", userId, ex.getMessage(), ex);
            return new TipsBundle(fallbackInsights, fallbackRecommendations);
        }
    }

    private List<String> buildRuleBasedInsights(List<DashboardSummaryResponse.AdherenceDTO> adherence) {
        if (adherence.isEmpty()) {
            return List.of("За выбранный период пока нет данных о приеме.");
        }

        int totalScheduled = adherence.stream().mapToInt(DashboardSummaryResponse.AdherenceDTO::getTotalScheduled).sum();
        int totalTaken = adherence.stream().mapToInt(DashboardSummaryResponse.AdherenceDTO::getTotalTaken).sum();
        double overall = totalScheduled == 0 ? 0.0 : round2(totalTaken * 100.0 / totalScheduled);

        List<String> insights = new ArrayList<>();
        insights.add("За период принято " + totalTaken + " из " + totalScheduled + " назначений (" + overall + "%).");

        if (overall >= 90) {
            insights.add("Отличный результат: вы соблюдаете схему приема почти без сбоев.");
        } else if (overall >= 75) {
            insights.add("Хорошо, но есть несколько пропусков. Лучше закрепить режим.");
        } else if (overall >= 50) {
            insights.add("Принято примерно половина доз. Попробуйте напоминания и фиксированное время приема.");
        } else {
            insights.add("Пропусков много. Стоит пересобрать режим, чтобы не пропускать приемы.");
        }

        long lowAdherenceCount = adherence.stream()
            .filter(item -> item.getAdherencePercent() < 80.0)
            .count();
        if (lowAdherenceCount == 0) {
            insights.add("Все лекарства держатся выше целевого уровня 80%.");
        } else {
            insights.add("Ниже цели 80% сейчас " + lowAdherenceCount + " препарат(а). Их важно подтянуть в первую очередь.");
        }

        long medicationsWithMissed = adherence.stream()
            .filter(item -> !item.getMissedDates().isEmpty())
            .count();
        if (medicationsWithMissed > 0) {
            insights.add("Есть пропуски по " + medicationsWithMissed + " препарат(у/ам). Проверьте ближайшие даты в календаре приема.");
        }

        return insights;
    }

    private List<String> buildRuleBasedRecommendations(List<DashboardSummaryResponse.AdherenceDTO> adherence) {
        if (adherence.isEmpty()) {
            return defaultGeneralRecommendations();
        }

        int totalScheduled = adherence.stream().mapToInt(DashboardSummaryResponse.AdherenceDTO::getTotalScheduled).sum();
        int totalTaken = adherence.stream().mapToInt(DashboardSummaryResponse.AdherenceDTO::getTotalTaken).sum();
        double overall = totalScheduled == 0 ? 0.0 : round2(totalTaken * 100.0 / totalScheduled);

        List<String> recommendations = new ArrayList<>();
        if (overall < 80) {
            recommendations.add("Привяжите прием лекарств к стабильной ежедневной привычке, например к завтраку или ужину.");
            recommendations.add("Если пропускаете дозы, включите 1-2 напоминания с интервалом 15-30 минут.");
        } else {
            recommendations.add("Продолжайте принимать лекарства в то же время каждый день, это поддерживает стабильный эффект.");
        }

        boolean hasMissed = adherence.stream().anyMatch(item -> !item.getMissedDates().isEmpty());
        if (hasMissed) {
            recommendations.add("Проверьте пропущенные даты в календаре и запланируйте ближайший прием по назначению врача.");
        }

        if (recommendations.size() < 3) {
            recommendations.add("Пейте достаточно воды в течение дня и старайтесь хорошо высыпаться.");
        }

        return recommendations.stream().limit(3).toList();
    }

    private List<String> defaultGeneralRecommendations() {
        return List.of(
            "Пейте достаточно воды в течение дня.",
            "Старайтесь ложиться спать и просыпаться в одно и то же время.",
            "Принимайте лекарства строго по схеме, которую назначил врач."
        );
    }

    private double round2(double value) {
        return Math.round(value * 100.0) / 100.0;
    }

    private static class MedicationStats {
        private int totalScheduled;
        private int totalTaken;
        private final List<String> missedDates = new ArrayList<>();
    }

    private static class DailyStats {
        private int taken;
        private int waiting;
        private int missed;
        private int totalScheduled;
    }

    private static class TipsBundle {
        private final List<String> insights;
        private final List<String> recommendations;

        private TipsBundle(List<String> insights, List<String> recommendations) {
            this.insights = insights;
            this.recommendations = recommendations;
        }
    }
}
