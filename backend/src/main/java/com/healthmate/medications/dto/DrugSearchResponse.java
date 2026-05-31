package com.healthmate.medications.dto;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.math.BigDecimal;
import java.util.List;
import java.util.UUID;

@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class DrugSearchResponse {

    private List<DrugSearchItem> results;

    @Data
    @NoArgsConstructor
    @AllArgsConstructor
    @Builder
    public static class DrugSearchItem {
        private UUID id;
        private String tradeName;
        private String internationalName;
        private String atxCode;
        private String doseUnit;
        private BigDecimal minDose;
        private BigDecimal maxDose;
        private Boolean isInRag;
        private Boolean hasMedia;
    }
}
