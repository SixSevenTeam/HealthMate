package com.healthmate.aigateway.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.UUID;

@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class AiTipsInvalidateRequest {

    @JsonProperty("userId")
    private UUID userId;

    @JsonProperty("reason")
    private String reason;
}
