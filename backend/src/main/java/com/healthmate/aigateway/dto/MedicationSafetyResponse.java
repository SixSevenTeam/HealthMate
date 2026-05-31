package com.healthmate.aigateway.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.Collections;
import java.util.List;
import java.util.Map;

@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class MedicationSafetyResponse {

    @JsonProperty("status")
    private String status;

    @JsonProperty("warnings")
    private List<String> warnings;

    @JsonProperty("blockers")
    private List<String> blockers;

    @JsonProperty("metadata")
    private Map<String, Object> metadata;

    public static MedicationSafetyResponse unavailable(String warning) {
        return MedicationSafetyResponse.builder()
            .status("unavailable")
            .warnings(Collections.singletonList(warning))
            .blockers(Collections.emptyList())
            .metadata(Collections.emptyMap())
            .build();
    }

    public List<String> safeWarnings() {
        return warnings == null ? Collections.emptyList() : warnings;
    }

    public List<String> safeBlockers() {
        return blockers == null ? Collections.emptyList() : blockers;
    }

    public String normalizedStatus() {
        if (status == null || status.isBlank()) {
            return "unknown";
        }
        return status.trim().toLowerCase();
    }
}