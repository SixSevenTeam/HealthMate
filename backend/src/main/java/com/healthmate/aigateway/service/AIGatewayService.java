package com.healthmate.aigateway.service;

import com.healthmate.aigateway.dto.AiChatRequest;
import com.healthmate.aigateway.dto.AiChatResponse;
import com.healthmate.aigateway.dto.AiTipsInvalidateRequest;
import com.healthmate.aigateway.dto.AiTipsRequest;
import com.healthmate.aigateway.dto.AiTipsResponse;
import com.healthmate.aigateway.dto.MedicationSafetyRequest;
import com.healthmate.aigateway.dto.MedicationSafetyResponse;
import com.healthmate.exception.AiServiceUnavailableException;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.client.RestClientException;
import org.springframework.web.client.HttpStatusCodeException;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestTemplate;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.util.Collections;
import java.util.UUID;

@Slf4j
@Service
public class AIGatewayService {

    @Value("${python.service-url}")
    private String pythonServiceUrl;

    @Value("${python.internal-api-key}")
    private String internalApiKey;

    @Value("${python.request-timeout-ms}")
    private long timeoutMs;

    @Value("${python.retry-count:2}")
    private int retryCount;

    @Value("${python.retry-delay-ms:2000}")
    private long retryDelayMs;

    private final ObjectMapper objectMapper;
    private final HttpClient httpClient = HttpClient.newHttpClient();
    private final RestTemplate restTemplate = new RestTemplate();

    public AIGatewayService(ObjectMapper objectMapper) {
        this.objectMapper = objectMapper;
    }

    public AiChatResponse chat(AiChatRequest request) {
        String requestJson = null;
        try {
            requestJson = objectMapper.writeValueAsString(request);
            String url = pythonServiceUrl + "/ai/chat";

            HttpHeaders headers = new HttpHeaders();
            headers.setContentType(MediaType.APPLICATION_JSON);
            headers.set("X-Internal-Key", internalApiKey);

            HttpEntity<AiChatRequest> entity = new HttpEntity<>(request, headers);
            ResponseEntity<AiChatResponse> response = restTemplate.exchange(
                url,
                HttpMethod.POST,
                entity,
                AiChatResponse.class
            );

            if (!response.getStatusCode().is2xxSuccessful() || response.getBody() == null) {
                throw new AiServiceUnavailableException("Python service returned invalid response");
            }

            return response.getBody();
        } catch (HttpStatusCodeException e) {
            log.error("Python /ai/chat error: status={}, body={}", e.getStatusCode().value(), e.getResponseBodyAsString());

            // Fallback transport for 422/malformed-body edge cases
            if (e.getStatusCode().value() == 422 && requestJson != null) {
                try {
                    log.warn("Retrying /ai/chat with raw HttpClient transport...");
                    String responseBody = callPythonServiceWithRetry("/ai/chat", requestJson);
                    return objectMapper.readValue(responseBody, AiChatResponse.class);
                } catch (Exception retryEx) {
                    throw new AiServiceUnavailableException("Python service unavailable", retryEx);
                }
            }

            throw new AiServiceUnavailableException("Python service unavailable", e);
        } catch (Exception e) {
            log.error("Failed to deserialize Python response. Check field mismatches between Java DTO and Python model", e);
            throw new AiServiceUnavailableException("Failed to parse AI response", e);
        }
    }

    public String indexDrug(String drugIndexRequest) {
        return callPythonServiceWithRetry("/ai/drugs/index", drugIndexRequest);
    }

    public String getDrugMedia(String drugId) {
        try {
            return callPythonService("/ai/drugs/" + drugId + "/media", "GET", null);
        } catch (Exception e) {
            throw new AiServiceUnavailableException("Failed to get drug media", e);
        }
    }

    public MedicationSafetyResponse validateMedication(MedicationSafetyRequest request) {
        try {
            String url = pythonServiceUrl + "/ai/medications/validate";

            HttpHeaders headers = new HttpHeaders();
            headers.setContentType(MediaType.APPLICATION_JSON);
            headers.set("X-Internal-Key", internalApiKey);

            HttpEntity<MedicationSafetyRequest> entity = new HttpEntity<>(request, headers);
            ResponseEntity<MedicationSafetyResponse> response = restTemplate.exchange(
                url,
                HttpMethod.POST,
                entity,
                MedicationSafetyResponse.class
            );

            if (!response.getStatusCode().is2xxSuccessful() || response.getBody() == null) {
                return MedicationSafetyResponse.unavailable("Safety validation returned empty response");
            }

            return response.getBody();
        } catch (HttpStatusCodeException e) {
            log.warn("Python /ai/medications/validate error: status={}, body={}", e.getStatusCode().value(), e.getResponseBodyAsString());
            return MedicationSafetyResponse.unavailable("Safety validation is temporarily unavailable");
        } catch (Exception e) {
            log.warn("Python /ai/medications/validate call failed", e);
            return MedicationSafetyResponse.unavailable("Safety validation is temporarily unavailable");
        }
    }

    public AiTipsResponse generateTips(AiTipsRequest request) {
        try {
            String url = pythonServiceUrl + "/ai/tips/generate";
            String requestJson = objectMapper.writeValueAsString(request);

            log.info("Python /ai/tips/generate request payload: {}", requestJson);

            HttpHeaders headers = new HttpHeaders();
            headers.setContentType(MediaType.APPLICATION_JSON);
            headers.set("X-Internal-Key", internalApiKey);

            HttpEntity<AiTipsRequest> entity = new HttpEntity<>(request, headers);
            ResponseEntity<AiTipsResponse> response = restTemplate.exchange(
                url,
                HttpMethod.POST,
                entity,
                AiTipsResponse.class
            );

            if (!response.getStatusCode().is2xxSuccessful() || response.getBody() == null) {
                return AiTipsResponse.builder()
                    .insights(Collections.emptyList())
                    .recommendations(Collections.emptyList())
                    .source("unavailable")
                    .build();
            }

            return response.getBody();
        } catch (HttpStatusCodeException e) {
            log.warn("Python /ai/tips/generate error: status={}, body={}", e.getStatusCode().value(), e.getResponseBodyAsString());
            return AiTipsResponse.builder()
                .insights(Collections.emptyList())
                .recommendations(Collections.emptyList())
                .source("unavailable")
                .build();
        } catch (RestClientException e) {
            log.warn("Python /ai/tips/generate call failed", e);
            return AiTipsResponse.builder()
                .insights(Collections.emptyList())
                .recommendations(Collections.emptyList())
                .source("unavailable")
                .build();
        } catch (Exception e) {
            log.warn("Unexpected error while generating AI tips", e);
            return AiTipsResponse.builder()
                .insights(Collections.emptyList())
                .recommendations(Collections.emptyList())
                .source("unavailable")
                .build();
        }
    }

    public void invalidateTipsCache(UUID userId, String reason) {
        if (userId == null) {
            return;
        }
        try {
            String url = pythonServiceUrl + "/ai/tips/invalidate";

            HttpHeaders headers = new HttpHeaders();
            headers.setContentType(MediaType.APPLICATION_JSON);
            headers.set("X-Internal-Key", internalApiKey);

            AiTipsInvalidateRequest payload = AiTipsInvalidateRequest.builder()
                .userId(userId)
                .reason(reason)
                .build();

            HttpEntity<AiTipsInvalidateRequest> entity = new HttpEntity<>(payload, headers);
            restTemplate.exchange(url, HttpMethod.POST, entity, String.class);
        } catch (Exception e) {
            log.warn("Failed to invalidate AI tips cache for user={} reason={}", userId, reason, e);
        }
    }

    private String callPythonServiceWithRetry(String endpoint, String requestBody) {
        Exception lastException = null;

        for (int attempt = 1; attempt <= retryCount; attempt++) {
            try {
                return callPythonService(endpoint, "POST", requestBody);
            } catch (Exception e) {
                lastException = e;
                log.warn("Python service call failed (attempt {}/{}): {}", attempt, retryCount, e.getMessage());

                if (attempt < retryCount) {
                    try {
                        Thread.sleep(retryDelayMs);
                    } catch (InterruptedException ie) {
                        Thread.currentThread().interrupt();
                        break;
                    }
                }
            }
        }

        throw new AiServiceUnavailableException("Python service unavailable after " + retryCount + " attempts", lastException);
    }

    private String callPythonService(String endpoint, String method, String body) throws Exception {
        String url = pythonServiceUrl + endpoint;

        HttpRequest.Builder requestBuilder = HttpRequest.newBuilder()
            .uri(new URI(url))
            .header("X-Internal-Key", internalApiKey)
            .timeout(Duration.ofMillis(timeoutMs));

        if ("POST".equals(method)) {
            requestBuilder.header("Content-Type", "application/json")
                .POST(HttpRequest.BodyPublishers.ofString(body != null ? body : ""));
        } else {
            requestBuilder.GET();
        }

        HttpRequest request = requestBuilder.build();

        HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());

        if (response.statusCode() >= 400) {
            log.error("Python service error: {} - {}", response.statusCode(), response.body());
            throw new AiServiceUnavailableException(
                "Python service returned error: " + response.statusCode()
            );
        }

        return response.body();
    }
}
