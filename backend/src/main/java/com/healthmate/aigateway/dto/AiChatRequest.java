package com.healthmate.aigateway.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import com.healthmate.profile.service.UserContextDTO;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.List;
import java.util.Map;
import java.util.UUID;

@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class AiChatRequest {

    @JsonProperty("conversationId")
    private UUID conversationId;

    @JsonProperty("userMessage")
    private String userMessage;

    @JsonProperty("anamnesisState")
    private Map<String, Object> anamnesisState;

    @JsonProperty("userContext")
    private UserContextDTO userContext;

    @JsonProperty("conversationHistory")
    private List<HistoryMessage> conversationHistory;

    @Data
    @NoArgsConstructor
    @AllArgsConstructor
    public static class HistoryMessage {
        private String role;
        private String content;
    }
}
