package com.healthmate.profile.service;

import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;
import com.healthmate.profile.dto.AllergyDTO;
import com.healthmate.profile.dto.DiagnosisDTO;

import java.time.LocalDate;
import java.util.List;
import java.util.UUID;

@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class UserContextDTO {

    private UUID userId;

    @JsonProperty("birthDate")
    private LocalDate birthDate;

    @JsonProperty("heightCm")
    private Integer heightCm;

    @JsonProperty("weightKg")
    private java.math.BigDecimal weightKg;

    @JsonProperty("bloodType")
    private String bloodType;

    private List<DiagnosisDTO> diagnoses;
    private List<AllergyDTO> allergies;

    @JsonProperty("contextDegraded")
    private Boolean contextDegraded;

    @JsonProperty("contextWarnings")
    private List<String> contextWarnings;

    @JsonProperty("activeMedications")
    private List<ActiveMedicationDTO> activeMedications;

    @Data
    @NoArgsConstructor
    @AllArgsConstructor
    public static class ActiveMedicationDTO {
        @JsonProperty("tradeName")
        private String tradeName;

        @JsonProperty("internationalName")
        private String internationalName;

        @JsonProperty("doseAmount")
        private java.math.BigDecimal doseAmount;

        @JsonProperty("doseUnit")
        private String doseUnit;

        private String instructions;
    }
}
