package com.healthmate.aigateway.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.List;
import java.util.Map;

@Data
@NoArgsConstructor
@AllArgsConstructor
public class AiChatResponse {
    private String content;

    @JsonProperty("messageType")
    private String messageType;

    @JsonProperty("anamnesisState")
    private Map<String, Object> anamnesisState;

    @JsonProperty("drugReferenceId")
    private String drugReferenceId;

    @JsonProperty("ragSource")
    private String ragSource;

    @JsonProperty("recommendedDrugs")
    private List<Map<String, Object>> recommendedDrugs;

    private String disclaimer;
}
