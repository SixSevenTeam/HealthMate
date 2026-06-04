package com.healthmate.aigateway.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.Collections;
import java.util.List;

@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class AiTipsResponse {

    @JsonProperty("insights")
    private List<String> insights;

    @JsonProperty("recommendations")
    private List<String> recommendations;

    @JsonProperty("source")
    private String source;

    public List<String> safeInsights() {
        return insights == null ? Collections.emptyList() : insights;
    }

    public List<String> safeRecommendations() {
        return recommendations == null ? Collections.emptyList() : recommendations;
    }
}
