package com.healthmate.medications.dto;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.List;
import java.util.UUID;

@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class UserMedicationResponse {
    private UUID id;
    private String tradeName;
    private String customName;
    private BigDecimal doseAmount;
    private String doseUnit;
    private String instructions;
    private String doseWarning;
    private String safetyStatus;
    private List<String> safetyWarnings;
    private Boolean isActive;
    private LocalDate startDate;
    private LocalDate endDate;
    private List<MedicationScheduleResponse> schedules;
}
