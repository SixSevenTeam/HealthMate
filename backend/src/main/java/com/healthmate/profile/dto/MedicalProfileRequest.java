package com.healthmate.profile.dto;

import jakarta.validation.Valid;
import jakarta.validation.constraints.DecimalMin;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.Pattern;
import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.List;

@Data
@NoArgsConstructor
@AllArgsConstructor
public class MedicalProfileRequest {

    @Min(30)
    @Max(300)
    private Integer heightCm;

    @DecimalMin("1.0")
    private java.math.BigDecimal weightKg;

    @Pattern(regexp = "^(A|B|AB|O)[+-]$", message = "bloodType must match A+, A-, B+, B-, AB+, AB-, O+, O-")
    private String bloodType;

    @Valid
    private List<DiagnosisDTO> diagnoses;

    @Valid
    private List<AllergyDTO> allergies;
}
