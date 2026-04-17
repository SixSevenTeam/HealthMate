package com.healthmate.chat.controller;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.healthmate.aigateway.dto.AiChatRequest;
import com.healthmate.aigateway.dto.AiChatResponse;
import com.healthmate.aigateway.service.AIGatewayService;
import com.healthmate.auth.service.AuthService;
import com.healthmate.chat.entity.Conversation;
import com.healthmate.chat.entity.Message;
import com.healthmate.chat.service.ChatService;
import com.healthmate.exception.ErrorResponse;
import com.healthmate.medications.service.MedicationsService;
import com.healthmate.profile.service.ProfileService;
import com.healthmate.profile.service.UserContextDTO;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.media.ArraySchema;
import io.swagger.v3.oas.annotations.media.Content;
import io.swagger.v3.oas.annotations.media.ExampleObject;
import io.swagger.v3.oas.annotations.media.Schema;
import io.swagger.v3.oas.annotations.responses.ApiResponse;
import io.swagger.v3.oas.annotations.responses.ApiResponses;
import io.swagger.v3.oas.annotations.security.SecurityRequirement;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;
import java.util.UUID;

@RestController
@RequestMapping("/api/conversations")
@Tag(name = "Chat", description = "Conversation lifecycle and AI chat messages")
@SecurityRequirement(name = "cookieAuth")
public class ChatController {

    private final ChatService chatService;
    private final AIGatewayService aiGatewayService;
    private final ProfileService profileService;
    private final MedicationsService medicationsService;
    private final AuthService authService;
    private final ObjectMapper objectMapper;

    public ChatController(
        ChatService chatService,
        AIGatewayService aiGatewayService,
        ProfileService profileService,
        MedicationsService medicationsService,
        AuthService authService,
        ObjectMapper objectMapper
    ) {
        this.chatService = chatService;
        this.aiGatewayService = aiGatewayService;
        this.profileService = profileService;
        this.medicationsService = medicationsService;
        this.authService = authService;
        this.objectMapper = objectMapper;
    }

    @GetMapping
    @Operation(summary = "List conversations", description = "Returns paged conversations for current user")
    @ApiResponses(value = {
        @ApiResponse(responseCode = "200", description = "Conversations page"),
        @ApiResponse(responseCode = "401", description = "Unauthorized", content = @Content(schema = @Schema(implementation = ErrorResponse.class)))
    })
    public ResponseEntity<Page<Conversation>> getConversations(
        @RequestParam(defaultValue = "0") int page,
        @RequestParam(defaultValue = "20") int size) {

        UUID userId = getUserId();
        Page<Conversation> conversations = chatService.getUserConversations(userId, PageRequest.of(page, size));
        return ResponseEntity.ok(conversations);
    }

    @PostMapping
    @Operation(summary = "Create conversation", description = "Creates a new conversation for current user")
    @ApiResponses(value = {
        @ApiResponse(responseCode = "201", description = "Conversation created", content = @Content(schema = @Schema(implementation = Conversation.class))),
        @ApiResponse(responseCode = "401", description = "Unauthorized", content = @Content(schema = @Schema(implementation = ErrorResponse.class)))
    })
    public ResponseEntity<Conversation> createConversation(@RequestBody Map<String, String> request) {
        UUID userId = getUserId();
        String title = request.getOrDefault("title", "New Conversation");
        Conversation conversation = chatService.createConversation(userId, title);
        return ResponseEntity.status(HttpStatus.CREATED).body(conversation);
    }

    @GetMapping("/{conversationId}/messages")
    @Operation(summary = "List conversation messages", description = "Returns all messages for a conversation")
    @ApiResponses(value = {
        @ApiResponse(responseCode = "200", description = "Message list", content = @Content(array = @ArraySchema(schema = @Schema(implementation = Message.class)))),
        @ApiResponse(responseCode = "404", description = "Conversation not found", content = @Content(schema = @Schema(implementation = ErrorResponse.class))),
        @ApiResponse(responseCode = "401", description = "Unauthorized", content = @Content(schema = @Schema(implementation = ErrorResponse.class)))
    })
    public ResponseEntity<List<Message>> getMessages(@PathVariable UUID conversationId) {
        UUID userId = getUserId();
        List<Message> messages = chatService.getConversationMessages(conversationId, userId);
        return ResponseEntity.ok(messages);
    }

    @PostMapping("/{conversationId}/messages")
    @Operation(summary = "Send message", description = "Adds user message, invokes AI, and returns user/assistant messages with metadata")
    @ApiResponses(value = {
        @ApiResponse(responseCode = "200", description = "Message exchange completed", content = @Content(examples = @ExampleObject(value = "{\"userMessage\":{},\"assistantMessage\":{},\"messageType\":\"question\",\"disclaimer\":\"...\",\"recommendedDrugs\":[]}"))),
        @ApiResponse(responseCode = "404", description = "Conversation not found", content = @Content(schema = @Schema(implementation = ErrorResponse.class))),
        @ApiResponse(responseCode = "401", description = "Unauthorized", content = @Content(schema = @Schema(implementation = ErrorResponse.class))),
        @ApiResponse(responseCode = "503", description = "AI service unavailable", content = @Content(schema = @Schema(implementation = ErrorResponse.class)))
    })
    public ResponseEntity<?> sendMessage(
        @PathVariable UUID conversationId,
        @RequestBody Map<String, String> request) {

        UUID userId = getUserId();
        String userContent = request.get("content");

        // Add user message
        Message userMessage = chatService.addMessage(conversationId, userId, userContent, true);
        Conversation conversation = chatService.getConversation(conversationId, userId);

        UserContextDTO userContext = profileService.getUserContext(userId);
        userContext.setBirthDate(authService.getUserEntity(userId).getBirthDate());
        userContext.setActiveMedications(medicationsService.getActiveMedicationsForContext(userId));

        Map<String, Object> anamnesisState = conversation.getAnamnesisState();
        if (anamnesisState == null || anamnesisState.isEmpty()) {
            anamnesisState = Map.of("stage", "collecting");
        }
        List<AiChatRequest.HistoryMessage> history = chatService.getRecentMessages(conversationId, 10).stream()
            .map(msg -> new AiChatRequest.HistoryMessage(msg.getRole(), msg.getContent()))
            .toList();

        AiChatRequest aiRequest = AiChatRequest.builder()
            .conversationId(conversationId)
            .userMessage(userContent)
            .anamnesisState(anamnesisState)
            .userContext(userContext)
            .conversationHistory(history)
            .build();

        AiChatResponse aiResponse = aiGatewayService.chat(aiRequest);
        UUID drugReference = safeParseUuid(aiResponse.getDrugReferenceId());

        Message assistantMessage = chatService.addAssistantMessage(
            conversationId,
            userId,
            aiResponse.getContent(),
            drugReference,
            aiResponse.getRagSource()
        );

        if (aiResponse.getAnamnesisState() != null) {
            chatService.updateConversationAnamnesisState(conversationId, aiResponse.getAnamnesisState());
        }

        Map<String, Object> response = new java.util.HashMap<>();
        response.put("userMessage", userMessage);
        response.put("assistantMessage", assistantMessage);
        response.put("messageType", aiResponse.getMessageType());
        response.put("disclaimer", aiResponse.getDisclaimer());
        response.put("recommendedDrugs", aiResponse.getRecommendedDrugs());
        return ResponseEntity.ok(response);
    }

    @DeleteMapping("/{conversationId}")
    @Operation(summary = "Delete conversation", description = "Deletes conversation and all related messages")
    @ApiResponses(value = {
        @ApiResponse(responseCode = "200", description = "Deleted", content = @Content(examples = @ExampleObject(value = "{\"message\":\"Conversation deleted\"}"))),
        @ApiResponse(responseCode = "404", description = "Conversation not found", content = @Content(schema = @Schema(implementation = ErrorResponse.class))),
        @ApiResponse(responseCode = "401", description = "Unauthorized", content = @Content(schema = @Schema(implementation = ErrorResponse.class)))
    })
    public ResponseEntity<?> deleteConversation(@PathVariable UUID conversationId) {
        UUID userId = getUserId();
        chatService.deleteConversation(conversationId, userId);
        return ResponseEntity.ok(Map.of("message", "Conversation deleted"));
    }

    private UUID getUserId() {
        Object principal = SecurityContextHolder.getContext().getAuthentication().getPrincipal();
        return UUID.fromString((String) principal);
    }

    private UUID safeParseUuid(String value) {
        if (value == null || value.isBlank()) {
            return null;
        }
        try {
            return UUID.fromString(value);
        } catch (IllegalArgumentException ex) {
            return null;
        }
    }

}
