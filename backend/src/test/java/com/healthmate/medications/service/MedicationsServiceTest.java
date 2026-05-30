package com.healthmate.medications.service;


import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;

import java.math.BigDecimal;
import java.time.Instant;
import java.time.LocalTime;
import java.util.List;
import java.util.Optional;
import java.util.UUID;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import com.healthmate.exception.ResourceNotFoundException;
import com.healthmate.medications.entity.Drug;
import com.healthmate.medications.entity.IntakeLog;
import com.healthmate.medications.entity.Schedule;
import com.healthmate.medications.entity.UserMedication;
import com.healthmate.medications.repository.DrugRepository;
import com.healthmate.medications.repository.IntakeLogRepository;
import com.healthmate.medications.repository.ScheduleRepository;
import com.healthmate.medications.repository.UserMedicationRepository;


@ExtendWith(MockitoExtension.class)
class MedicationsServiceTest {

    @Mock
    DrugRepository drugRepository;
    @Mock
    UserMedicationRepository userMedicationRepository;
    @Mock
    ScheduleRepository scheduleRepository;
    @Mock
    IntakeLogRepository intakeLogRepository;

    MedicationsService service;

    @BeforeEach
    void setUp() {
        service = new MedicationsService(
                drugRepository,
                userMedicationRepository,
                scheduleRepository,
                intakeLogRepository);
    }

    @Test
    void searchDrugs_delegatesToRepository() {
        Drug drug = buildDrug(
                "ÐŸÐ°Ñ€Ð°Ñ†ÐµÑ‚Ð°Ð¼Ð¾Ð»",
                "Paracetamol",
                "N02BE01",
                BigDecimal.valueOf(250),
                BigDecimal.valueOf(1000),
                "mg");
        when(drugRepository.searchByQuery("Ð¿Ð°Ñ€Ð°Ñ†ÐµÑ‚Ð°Ð¼Ð¾Ð»")).thenReturn(List.of(drug));

        List<Drug> result = service.searchDrugs("Ð¿Ð°Ñ€Ð°Ñ†ÐµÑ‚Ð°Ð¼Ð¾Ð»");

        assertThat(result).hasSize(1);
        assertThat(result.get(0).getTradeName()).isEqualTo("ÐŸÐ°Ñ€Ð°Ñ†ÐµÑ‚Ð°Ð¼Ð¾Ð»");
    }

    @Test
    void searchDrugs_noResults_returnsEmpty() {
        when(drugRepository.searchByQuery("xyz123abc")).thenReturn(List.of());
        assertThat(service.searchDrugs("xyz123abc")).isEmpty();
    }

    @Test
    void getDrugById_found_returnsDrug() {
        UUID drugId = UUID.randomUUID();
        Drug drug = buildDrug(
                "ÐÑÐ¿Ð¸Ñ€Ð¸Ð½",
                "Aspirin",
                "B01AC06",
                BigDecimal.valueOf(75),
                BigDecimal.valueOf(500),
                "mg");
        when(drugRepository.findById(drugId)).thenReturn(Optional.of(drug));

        Drug result = service.getDrugById(drugId);
        assertThat(result.getTradeName()).isEqualTo("ÐÑÐ¿Ð¸Ñ€Ð¸Ð½");
    }

    @Test
    void getDrugById_notFound_throwsResourceNotFound() {
        UUID drugId = UUID.randomUUID();
        when(drugRepository.findById(drugId)).thenReturn(Optional.empty());

        assertThatThrownBy(() -> service.getDrugById(drugId)).isInstanceOf(ResourceNotFoundException.class);
    }

    @Test
    void calculateDoseWarning_belowMin_returnsWarning() {
        UUID drugId = UUID.randomUUID();
        Drug drug = buildDrug("Ð˜Ð±ÑƒÐ¿Ñ€Ð¾Ñ„ÐµÐ½", null, null, BigDecimal.valueOf(200), BigDecimal.valueOf(800), "mg");
        UserMedication med = buildMedication(drugId, BigDecimal.valueOf(100), "mg");

        when(drugRepository.findById(drugId)).thenReturn(Optional.of(drug));

        String warning = service.calculateDoseWarning(med);
        assertThat(warning).isEqualTo("Dose is below minimum recommended");
    }

    @Test
    void calculateDoseWarning_aboveMax_returnsWarning() {
        UUID drugId = UUID.randomUUID();
        Drug drug = buildDrug("Ð˜Ð±ÑƒÐ¿Ñ€Ð¾Ñ„ÐµÐ½", null, null, BigDecimal.valueOf(200), BigDecimal.valueOf(800), "mg");
        UserMedication med = buildMedication(drugId, BigDecimal.valueOf(1200), "mg");

        when(drugRepository.findById(drugId)).thenReturn(Optional.of(drug));

        String warning = service.calculateDoseWarning(med);
        assertThat(warning).isEqualTo("Dose is above maximum recommended");
    }

    @Test
    void calculateDoseWarning_withinRange_returnsNull() {
        UUID drugId = UUID.randomUUID();
        Drug drug = buildDrug("Ð˜Ð±ÑƒÐ¿Ñ€Ð¾Ñ„ÐµÐ½", null, null, BigDecimal.valueOf(200), BigDecimal.valueOf(800), "mg");
        UserMedication med = buildMedication(drugId, BigDecimal.valueOf(400), "mg");

        when(drugRepository.findById(drugId)).thenReturn(Optional.of(drug));

        assertThat(service.calculateDoseWarning(med)).isNull();
    }

    @Test
    void calculateDoseWarning_noDrugId_returnsNull() {
        UserMedication med = UserMedication.builder().id(UUID.randomUUID()).customName("Custom pill").doseAmount(
                BigDecimal.valueOf(500)).doseUnit("mg").build();

        assertThat(service.calculateDoseWarning(med)).isNull();
        verifyNoInteractions(drugRepository);
    }

    @Test
    void calculateDoseWarning_noDoseAmount_returnsNull() {
        UUID drugId = UUID.randomUUID();
        UserMedication med = UserMedication.builder().id(UUID.randomUUID()).drugId(drugId).doseUnit("mg").build();

        assertThat(service.calculateDoseWarning(med)).isNull();
    }

    @Test
    void calculateDoseWarning_drugNotFound_returnsNull() {
        UUID drugId = UUID.randomUUID();
        UserMedication med = buildMedication(drugId, BigDecimal.valueOf(400), "mg");
        when(drugRepository.findById(drugId)).thenReturn(Optional.empty());

        assertThat(service.calculateDoseWarning(med)).isNull();
    }

    @Test
    void resolveTradeName_hasDrugId_returnsFromDb() {
        UUID drugId = UUID.randomUUID();
        Drug drug = buildDrug("ÐŸÐ°Ñ€Ð°Ñ†ÐµÑ‚Ð°Ð¼Ð¾Ð»", null, null, null, null, null);
        UserMedication med = buildMedication(drugId, BigDecimal.ONE, "mg");

        when(drugRepository.findById(drugId)).thenReturn(Optional.of(drug));

        assertThat(service.resolveTradeName(med)).isEqualTo("ÐŸÐ°Ñ€Ð°Ñ†ÐµÑ‚Ð°Ð¼Ð¾Ð»");
    }

    @Test
    void resolveTradeName_drugNotFound_fallsBackToCustomName() {
        UUID drugId = UUID.randomUUID();
        UserMedication med = UserMedication.builder().id(UUID.randomUUID()).drugId(drugId).customName(
                "ÐœÐ¾Ð¹ Ð¿Ñ€ÐµÐ¿Ð°Ñ€Ð°Ñ‚").doseAmount(BigDecimal.ONE).doseUnit("mg").build();
        when(drugRepository.findById(drugId)).thenReturn(Optional.empty());

        assertThat(service.resolveTradeName(med)).isEqualTo("ÐœÐ¾Ð¹ Ð¿Ñ€ÐµÐ¿Ð°Ñ€Ð°Ñ‚");
    }

    @Test
    void resolveTradeName_noDrugId_returnsCustomName() {
        UserMedication med = UserMedication.builder().id(UUID.randomUUID()).customName("Ð’Ð¸Ñ‚Ð°Ð¼Ð¸Ð½ D").doseAmount(
                BigDecimal.ONE).doseUnit("mg").build();

        assertThat(service.resolveTradeName(med)).isEqualTo("Ð’Ð¸Ñ‚Ð°Ð¼Ð¸Ð½ D");
        verifyNoInteractions(drugRepository);
    }

    @Test
    void deactivateMedication_found_setsInactiveAndDeletesPendingLogs() {
        UUID userId = UUID.randomUUID();
        UUID medId = UUID.randomUUID();
        UserMedication med = buildMedicationWithUser(medId, userId);
        med.setIsActive(true);

        when(userMedicationRepository.findByIdAndUserId(medId, userId)).thenReturn(Optional.of(med));
        when(userMedicationRepository.save(any())).thenReturn(med);

        service.deactivateUserMedication(medId, userId);

        assertThat(med.getIsActive()).isFalse();
        verify(intakeLogRepository).deleteByUserMedicationIdAndStatusAndScheduledAtGreaterThan(
                eq(medId),
                eq("pending"),
                any(Instant.class));
    }

    @Test
    void deactivateMedication_notFound_throwsResourceNotFound() {
        UUID userId = UUID.randomUUID();
        UUID medId = UUID.randomUUID();
        when(userMedicationRepository.findByIdAndUserId(medId, userId)).thenReturn(Optional.empty());

        assertThatThrownBy(() -> service.deactivateUserMedication(medId, userId)).isInstanceOf(
                ResourceNotFoundException.class);
    }

    @Test
    void setIntakeStatus_taken_setsTakenAt() {
        UUID userId = UUID.randomUUID();
        UUID logId = UUID.randomUUID();
        UUID medId = UUID.randomUUID();
        UserMedication med = buildMedicationWithUser(medId, userId);
        Instant scheduledAt = Instant.now().minusSeconds(3600);
        IntakeLog log = buildIntakeLog(logId, medId, scheduledAt);

        when(intakeLogRepository.findById(logId)).thenReturn(Optional.of(log));
        when(userMedicationRepository.findByIdAndUserId(medId, userId)).thenReturn(Optional.of(med));
        when(intakeLogRepository.save(any())).thenAnswer(inv -> inv.getArgument(0));

        IntakeLog result = service.setIntakeStatus(logId, userId, "taken");

        assertThat(result.getStatus()).isEqualTo("taken");
        assertThat(result.getTakenAt()).isNotNull();
        assertThat(result.getConfirmedVia()).isEqualTo("app");
    }

    @Test
    void setIntakeStatus_missed_clearsFields() {
        UUID userId = UUID.randomUUID();
        UUID logId = UUID.randomUUID();
        UUID medId = UUID.randomUUID();
        UserMedication med = buildMedicationWithUser(medId, userId);
        IntakeLog log = buildIntakeLog(logId, medId, Instant.now().minusSeconds(3600));

        when(intakeLogRepository.findById(logId)).thenReturn(Optional.of(log));
        when(userMedicationRepository.findByIdAndUserId(medId, userId)).thenReturn(Optional.of(med));
        when(intakeLogRepository.save(any())).thenAnswer(inv -> inv.getArgument(0));

        IntakeLog result = service.setIntakeStatus(logId, userId, "missed");

        assertThat(result.getStatus()).isEqualTo("missed");
        assertThat(result.getTakenAt()).isNull();
    }

    @Test
    void setIntakeStatus_invalidStatus_throwsIllegalArgument() {
        UUID userId = UUID.randomUUID();
        UUID logId = UUID.randomUUID();
        UUID medId = UUID.randomUUID();
        UserMedication med = buildMedicationWithUser(medId, userId);
        IntakeLog log = buildIntakeLog(logId, medId, Instant.now());

        when(intakeLogRepository.findById(logId)).thenReturn(Optional.of(log));
        when(userMedicationRepository.findByIdAndUserId(medId, userId)).thenReturn(Optional.of(med));

        assertThatThrownBy(() -> service.setIntakeStatus(logId, userId, "INVALID")).isInstanceOf(
                IllegalArgumentException.class);
    }

    @Test
    void setIntakeStatus_logNotFound_throwsResourceNotFound() {
        UUID logId = UUID.randomUUID();
        when(intakeLogRepository.findById(logId)).thenReturn(Optional.empty());

        assertThatThrownBy(() -> service.setIntakeStatus(logId, UUID.randomUUID(), "taken")).isInstanceOf(
                ResourceNotFoundException.class);
    }

    @Test
    void createMedicationWithSchedules_noSchedules_throwsIllegalArgument() {
        UUID userId = UUID.randomUUID();
        UserMedication med = UserMedication.builder().drugId(UUID.randomUUID()).doseAmount(BigDecimal.ONE).doseUnit(
                "mg").isActive(true).build();

        assertThatThrownBy(() -> service.createMedicationWithSchedules(userId, med, List.of())).isInstanceOf(
                IllegalArgumentException.class);
    }

    @Test
    void createMedicationWithSchedules_noDrugAndNoCustomName_throwsIllegalArgument() {
        UUID userId = UUID.randomUUID();
        UserMedication med = UserMedication.builder().doseAmount(BigDecimal.ONE).doseUnit("mg").isActive(true).build();
        Schedule schedule = Schedule.builder().timeOfDay(LocalTime.of(9, 0)).daysOfWeek(new Integer[] { 1, 2, 3 })
                .build();

        assertThatThrownBy(() -> service.createMedicationWithSchedules(userId, med, List.of(schedule))).isInstanceOf(
                IllegalArgumentException.class);
    }

    @Test
    void getActiveMedicationsForContext_hasDrug_resolvesTradeName() {
        UUID userId = UUID.randomUUID();
        UUID drugId = UUID.randomUUID();
        UserMedication med = buildMedicationWithUser(UUID.randomUUID(), userId);
        med.setDrugId(drugId);
        Drug drug = buildDrug(
                "ÐœÐµÑ‚Ñ„Ð¾Ñ€Ð¼Ð¸Ð½",
                "Metformin",
                "A10BA02",
                BigDecimal.valueOf(500),
                BigDecimal.valueOf(2000),
                "mg");

        when(userMedicationRepository.findByUserIdAndIsActive(userId, true)).thenReturn(List.of(med));
        when(drugRepository.findById(drugId)).thenReturn(Optional.of(drug));

        var result = service.getActiveMedicationsForContext(userId);

        assertThat(result).hasSize(1);
        assertThat(result.get(0).getTradeName()).isEqualTo("ÐœÐµÑ‚Ñ„Ð¾Ñ€Ð¼Ð¸Ð½");
        assertThat(result.get(0).getInternationalName()).isEqualTo("Metformin");
    }

    @Test
    void getActiveMedicationsForContext_noMedications_returnsEmpty() {
        UUID userId = UUID.randomUUID();
        when(userMedicationRepository.findByUserIdAndIsActive(userId, true)).thenReturn(List.of());

        var result = service.getActiveMedicationsForContext(userId);
        assertThat(result).isEmpty();
    }

    private Drug buildDrug(
            String tradeName,
            String internationalName,
            String atxCode,
            BigDecimal minDose,
            BigDecimal maxDose,
            String doseUnit) {
        return Drug.builder().id(UUID.randomUUID()).tradeName(tradeName).internationalName(internationalName).atxCode(
                atxCode).minDose(minDose).maxDose(maxDose).doseUnit(doseUnit).isInRag(false).build();
    }

    private UserMedication buildMedication(UUID drugId, BigDecimal dose, String unit) {
        return UserMedication.builder().id(UUID.randomUUID()).drugId(drugId).doseAmount(dose).doseUnit(unit).isActive(
                true).build();
    }

    private UserMedication buildMedicationWithUser(UUID medId, UUID userId) {
        return UserMedication.builder().id(medId).userId(userId).drugId(UUID.randomUUID()).doseAmount(
                BigDecimal.valueOf(100)).doseUnit("mg").isActive(true).build();
    }

    private IntakeLog buildIntakeLog(UUID logId, UUID medId, Instant scheduledAt) {
        return IntakeLog.builder().id(logId).userMedicationId(medId).scheduledAt(scheduledAt).status("pending").build();
    }
}