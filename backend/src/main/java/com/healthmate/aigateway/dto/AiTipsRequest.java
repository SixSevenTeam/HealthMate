package com.healthmate.aigateway.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import com.healthmate.profile.service.UserContextDTO;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDate;
import java.util.List;
import java.util.UUID;

@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class AiTipsRequest {

    @JsonProperty("userId")
    private UUID userId;

    @JsonProperty("from")
    private LocalDate from;

    @JsonProperty("to")
    private LocalDate to;

    @JsonProperty("scope")
    private String scope;

    @JsonProperty("userContext")
    private UserContextDTO userContext;

    @JsonProperty("overallAdherence")
    private double overallAdherence;

    @JsonProperty("totalScheduled")
    private int totalScheduled;

    @JsonProperty("totalTaken")
    private int totalTaken;

    @JsonProperty("adherence")
    private List<AdherenceItem> adherence;

    @Data
    @NoArgsConstructor
    @AllArgsConstructor
    @Builder
    public static class AdherenceItem {
        @JsonProperty("tradeName")
        private String tradeName;

        @JsonProperty("totalScheduled")
        private int totalScheduled;

        @JsonProperty("totalTaken")
        private int totalTaken;

        @JsonProperty("adherencePercent")
        private double adherencePercent;

        @JsonProperty("missedDates")
        private List<String> missedDates;
    }
}
