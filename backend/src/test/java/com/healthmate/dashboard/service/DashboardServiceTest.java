package com.healthmate.dashboard.service;


import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.when;

import java.math.BigDecimal;
import java.time.Instant;
import java.time.LocalDate;
import java.time.LocalTime;
import java.time.ZoneId;
import java.util.List;
import java.util.UUID;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.data.domain.PageImpl;
import org.springframework.data.domain.Pageable;

import com.healthmate.medications.entity.IntakeLog;
import com.healthmate.medications.entity.Schedule;
import com.healthmate.medications.entity.UserMedication;
import com.healthmate.medications.repository.DrugRepository;
import com.healthmate.medications.repository.IntakeLogRepository;
import com.healthmate.medications.repository.ScheduleRepository;
import com.healthmate.medications.repository.UserMedicationRepository;


@ExtendWith(MockitoExtension.class)
class DashboardServiceTest {

    @Mock
    IntakeLogRepository intakeLogRepository;
    @Mock
    UserMedicationRepository userMedicationRepository;
    @Mock
    ScheduleRepository scheduleRepository;
    @Mock
    DrugRepository drugRepository;

    DashboardService dashboardService;

    final UUID userId = UUID.randomUUID();
    final LocalDate from = LocalDate.now().minusDays(6);
    final LocalDate to = LocalDate.now();

    @BeforeEach
    void setUp() {
        dashboardService = new DashboardService(
                intakeLogRepository,
                userMedicationRepository,
                scheduleRepository,
                drugRepository);
    }

    @Test
    void getSummary_nullFrom_throwsIllegalArgument() {
        assertThatThrownBy(() -> dashboardService.getSummary(userId, null, to, "active")).isInstanceOf(
                IllegalArgumentException.class);
    }

    @Test
    void getSummary_nullTo_throwsIllegalArgument() {
        assertThatThrownBy(() -> dashboardService.getSummary(userId, from, null, "active")).isInstanceOf(
                IllegalArgumentException.class);
    }

    @Test
    void getSummary_toBeforeFrom_throwsIllegalArgument() {
        assertThatThrownBy(() -> dashboardService.getSummary(userId, to, from.minusDays(1), "active")).isInstanceOf(
                IllegalArgumentException.class);
    }

    @Test
    void getSummary_noMedications_returnsEmptyAdherence() {
        when(userMedicationRepository.findByUserId(eq(userId), any(Pageable.class))).thenReturn(
                new PageImpl<>(List.of()));

        DashboardSummaryResponse response = dashboardService.getSummary(userId, from, to, "active");

        assertThat(response.getAdherence()).isEmpty();
        assertThat(response.getDailySeries()).hasSize(7);
        assertThat(response.getInsights()).contains("No medications for selected filter.");
    }

    @Test
    void getSummary_inactiveScopeOnlyActive_returnsEmpty() {
        UserMedication activeMed = buildMedication(userId, true);
        when(userMedicationRepository.findByUserId(eq(userId), any(Pageable.class))).thenReturn(
                new PageImpl<>(List.of(activeMed)));

        DashboardSummaryResponse response = dashboardService.getSummary(userId, from, to, "inactive");

        assertThat(response.getAdherence()).isEmpty();
    }

    @Test
    void getSummary_emptyMedications_dailySeriesCoversAllDays() {
        when(userMedicationRepository.findByUserId(eq(userId), any(Pageable.class))).thenReturn(
                new PageImpl<>(List.of()));

        LocalDate start = LocalDate.of(2026, 1, 1);
        LocalDate end = LocalDate.of(2026, 1, 31);

        DashboardSummaryResponse response = dashboardService.getSummary(userId, start, end, "active");

        assertThat(response.getDailySeries()).hasSize(31);
    }

    @Test
    void getSummary_singleDay_dailySeriesHasOneEntry() {
        when(userMedicationRepository.findByUserId(eq(userId), any(Pageable.class))).thenReturn(
                new PageImpl<>(List.of()));

        DashboardSummaryResponse response = dashboardService.getSummary(userId, to, to, "active");

        assertThat(response.getDailySeries()).hasSize(1);
    }

    @Test
    void getSummary_scopeAll_includesBothActiveAndInactive() {
        UserMedication activeMed = buildMedication(userId, true);
        UserMedication inactiveMed = buildMedication(userId, false);

        when(userMedicationRepository.findByUserId(eq(userId), any(Pageable.class))).thenReturn(
                new PageImpl<>(List.of(activeMed, inactiveMed)));
        when(scheduleRepository.findByUserMedicationId(any())).thenReturn(List.of());
        when(
                intakeLogRepository.findByUserMedicationIdInAndScheduledAtGreaterThanEqualAndScheduledAtLessThan(
                        any(),
                        any(),
                        any())).thenReturn(List.of());
        when(drugRepository.findAllById(any())).thenReturn(List.of());

        DashboardSummaryResponse response = dashboardService.getSummary(userId, from, to, "all");

        assertThat(response.getAdherence()).hasSize(2);
    }

    @Test
    void getSummary_unknownScope_treatedAsActive() {
        UserMedication activeMed = buildMedication(userId, true);
        UserMedication inactiveMed = buildMedication(userId, false);

        when(userMedicationRepository.findByUserId(eq(userId), any(Pageable.class))).thenReturn(
                new PageImpl<>(List.of(activeMed, inactiveMed)));
        when(scheduleRepository.findByUserMedicationId(any())).thenReturn(List.of());
        when(
                intakeLogRepository.findByUserMedicationIdInAndScheduledAtGreaterThanEqualAndScheduledAtLessThan(
                        any(),
                        any(),
                        any())).thenReturn(List.of());
        when(drugRepository.findAllById(any())).thenReturn(List.of());

        DashboardSummaryResponse response = dashboardService.getSummary(userId, from, to, "GARBAGE_SCOPE");

        assertThat(response.getAdherence()).hasSize(1);
    }

    @Test
    void getSummary_allTaken_adherence100Percent() {
        ZoneId zone = ZoneId.systemDefault();
        LocalDate testDay = LocalDate.now().minusDays(1);
        LocalDate testFrom = testDay;
        LocalDate testTo = testDay;

        UserMedication med = buildMedication(userId, true);
        med.setStartDate(testDay.minusDays(30));

        Schedule schedule = buildSchedule(
                med.getId(),
                LocalTime.of(9, 0),
                new Integer[] { testDay.getDayOfWeek().getValue() });

        Instant scheduledAt = testDay.atTime(9, 0).atZone(zone).toInstant();
        IntakeLog takenLog = IntakeLog.builder().id(UUID.randomUUID()).userMedicationId(med.getId()).scheduledAt(
                scheduledAt).takenAt(scheduledAt).status("taken").build();

        when(userMedicationRepository.findByUserId(eq(userId), any(Pageable.class))).thenReturn(
                new PageImpl<>(List.of(med)));
        when(scheduleRepository.findByUserMedicationId(med.getId())).thenReturn(List.of(schedule));
        when(
                intakeLogRepository.findByUserMedicationIdInAndScheduledAtGreaterThanEqualAndScheduledAtLessThan(
                        any(),
                        any(),
                        any())).thenReturn(List.of(takenLog));
        when(drugRepository.findAllById(any())).thenReturn(List.of());

        DashboardSummaryResponse response = dashboardService.getSummary(userId, testFrom, testTo, "active");

        assertThat(response.getAdherence()).hasSize(1);
        assertThat(response.getAdherence().get(0).getAdherencePercent()).isEqualTo(100.0);
        assertThat(response.getAdherence().get(0).getTotalTaken()).isEqualTo(1);
        assertThat(response.getAdherence().get(0).getTotalScheduled()).isEqualTo(1);
    }

    @Test
    void getSummary_allMissed_adherence0Percent() {
        ZoneId zone = ZoneId.systemDefault();
        LocalDate testDay = LocalDate.now().minusDays(1);

        UserMedication med = buildMedication(userId, true);
        Schedule schedule = buildSchedule(
                med.getId(),
                LocalTime.of(9, 0),
                new Integer[] { testDay.getDayOfWeek().getValue() });

        when(userMedicationRepository.findByUserId(eq(userId), any(Pageable.class))).thenReturn(
                new PageImpl<>(List.of(med)));
        when(scheduleRepository.findByUserMedicationId(med.getId())).thenReturn(List.of(schedule));
        when(
                intakeLogRepository.findByUserMedicationIdInAndScheduledAtGreaterThanEqualAndScheduledAtLessThan(
                        any(),
                        any(),
                        any())).thenReturn(List.of());
        when(drugRepository.findAllById(any())).thenReturn(List.of());

        DashboardSummaryResponse response = dashboardService.getSummary(userId, testDay, testDay, "active");

        assertThat(response.getAdherence().get(0).getAdherencePercent()).isEqualTo(0.0);
        assertThat(response.getAdherence().get(0).getMissedDates()).contains(testDay.toString());
    }

    @Test
    void getSummary_insights_containOverallAdherence() {
        when(userMedicationRepository.findByUserId(eq(userId), any(Pageable.class))).thenReturn(
                new PageImpl<>(List.of()));

        DashboardSummaryResponse response = dashboardService.getSummary(userId, from, to, "active");

        assertThat(response.getInsights()).anyMatch(s -> s.contains("No medications"));
    }

    @Test
    void getSummary_period_matchesRequestedDates() {
        when(userMedicationRepository.findByUserId(eq(userId), any(Pageable.class))).thenReturn(
                new PageImpl<>(List.of()));

        DashboardSummaryResponse response = dashboardService.getSummary(userId, from, to, "active");

        assertThat(response.getPeriod().getFrom()).isEqualTo(from);
        assertThat(response.getPeriod().getTo()).isEqualTo(to);
    }

    private UserMedication buildMedication(UUID userId, boolean isActive) {
        return UserMedication.builder().id(UUID.randomUUID()).userId(userId).drugId(null).customName(
                "Ð¢ÐµÑÑ‚Ð¾Ð²Ñ‹Ð¹ Ð¿Ñ€ÐµÐ¿Ð°Ñ€Ð°Ñ‚").doseAmount(BigDecimal.valueOf(100)).doseUnit("mg").isActive(
                        isActive).build();
    }

    private Schedule buildSchedule(UUID medId, LocalTime time, Integer[] days) {
        return Schedule.builder().id(UUID.randomUUID()).userMedicationId(medId).timeOfDay(time).daysOfWeek(days)
                .build();
    }
}