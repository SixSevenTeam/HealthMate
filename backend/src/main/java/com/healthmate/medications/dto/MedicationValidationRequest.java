package com.healthmate.medications.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.UUID;

@Data
@NoArgsConstructor
@AllArgsConstructor
public class MedicationValidationRequest {

    private UUID drugId;
    private String customName;

    @NotNull
    private BigDecimal doseAmount;

    @NotBlank
    private String doseUnit;

    private String instructions;
    private LocalDate startDate;
    private LocalDate endDate;
}