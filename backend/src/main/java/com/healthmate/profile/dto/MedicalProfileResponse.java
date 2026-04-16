package com.healthmate.profile.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.Instant;
import java.util.List;

@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class MedicalProfileResponse {
    private Integer heightCm;
    private java.math.BigDecimal weightKg;
    private String bloodType;
    private List<DiagnosisDTO> diagnoses;
    private List<AllergyDTO> allergies;

    @JsonProperty("updatedAt")
    private Instant updatedAt;
}
