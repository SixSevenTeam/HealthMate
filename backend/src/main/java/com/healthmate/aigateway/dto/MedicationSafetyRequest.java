package com.healthmate.aigateway.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import com.healthmate.profile.service.UserContextDTO;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.UUID;

@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class MedicationSafetyRequest {

    @JsonProperty("userId")
    private UUID userId;

    @JsonProperty("userContext")
    private UserContextDTO userContext;

    @JsonProperty("candidateMedication")
    private CandidateMedication candidateMedication;

    @Data
    @NoArgsConstructor
    @AllArgsConstructor
    @Builder
    public static class CandidateMedication {
        @JsonProperty("drugId")
        private UUID drugId;

        @JsonProperty("customName")
        private String customName;

        @JsonProperty("doseAmount")
        private BigDecimal doseAmount;

        @JsonProperty("doseUnit")
        private String doseUnit;

        @JsonProperty("instructions")
        private String instructions;

        @JsonProperty("startDate")
        private LocalDate startDate;

        @JsonProperty("endDate")
        private LocalDate endDate;
    }
}