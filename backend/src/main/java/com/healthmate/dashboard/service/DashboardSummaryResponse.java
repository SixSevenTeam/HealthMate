package com.healthmate.dashboard.service;

import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDate;
import java.util.List;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class DashboardSummaryResponse {

    private PeriodDTO period;

    @JsonProperty("adherence")
    private List<AdherenceDTO> adherence;

    @JsonProperty("insights")
    private List<String> insights;

    @JsonProperty("recommendations")
    private List<String> recommendations;

    @JsonProperty("dailySeries")
    private List<DailySeriesDTO> dailySeries;

    @Data
    @NoArgsConstructor
    @AllArgsConstructor
    public static class PeriodDTO {
        private LocalDate from;
        private LocalDate to;
    }

    @Data
    @NoArgsConstructor
    @AllArgsConstructor
    public static class AdherenceDTO {
        @JsonProperty("medicationId")
        private String medicationId;

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

    @Data
    @NoArgsConstructor
    @AllArgsConstructor
    public static class DailySeriesDTO {
        @JsonProperty("date")
        private LocalDate date;

        @JsonProperty("taken")
        private int taken;

        @JsonProperty("waiting")
        private int waiting;

        @JsonProperty("missed")
        private int missed;

        @JsonProperty("totalScheduled")
        private int totalScheduled;
    }
}
