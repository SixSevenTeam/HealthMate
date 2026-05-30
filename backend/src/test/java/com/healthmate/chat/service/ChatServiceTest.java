package com.healthmate.chat.service;


import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.argThat;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageImpl;
import org.springframework.data.domain.PageRequest;

import com.healthmate.chat.entity.Conversation;
import com.healthmate.chat.entity.Message;
import com.healthmate.chat.repository.ConversationRepository;
import com.healthmate.chat.repository.MessageRepository;
import com.healthmate.exception.ResourceNotFoundException;


@ExtendWith(MockitoExtension.class)
class ChatServiceTest {

    @Mock
    ConversationRepository conversationRepository;
    @Mock
    MessageRepository messageRepository;

    ChatService chatService;

    @BeforeEach
    void setUp() {
        chatService = new ChatService(conversationRepository, messageRepository);
    }

    @Test
    void createConversation_withTitle_savesCorrectly() {
        UUID userId = UUID.randomUUID();
        Conversation saved = buildConversation(userId, "ÐœÐ¾Ñ ÐºÐ¾Ð½ÑÑƒÐ»ÑŒÑ‚Ð°Ñ†Ð¸Ñ");
        when(conversationRepository.save(any())).thenReturn(saved);

        Conversation result = chatService.createConversation(userId, "ÐœÐ¾Ñ ÐºÐ¾Ð½ÑÑƒÐ»ÑŒÑ‚Ð°Ñ†Ð¸Ñ");

        assertThat(result.getTitle()).isEqualTo("ÐœÐ¾Ñ ÐºÐ¾Ð½ÑÑƒÐ»ÑŒÑ‚Ð°Ñ†Ð¸Ñ");
        assertThat(result.getUserId()).isEqualTo(userId);
        assertThat(result.getStatus()).isEqualTo("active");
    }

    @Test
    void createConversation_nullTitle_usesDefault() {
        UUID userId = UUID.randomUUID();
        Conversation saved = buildConversation(userId, "New Conversation");
        when(conversationRepository.save(any())).thenReturn(saved);

        Conversation result = chatService.createConversation(userId, null);

        assertThat(result.getTitle()).isEqualTo("New Conversation");
    }

    @Test
    void getUserConversations_returnsPaged() {
        UUID userId = UUID.randomUUID();
        Conversation conv = buildConversation(userId, "Test");
        Page<Conversation> page = new PageImpl<>(List.of(conv));
        when(conversationRepository.findByUserId(eq(userId), any())).thenReturn(page);

        Page<Conversation> result = chatService.getUserConversations(userId, PageRequest.of(0, 20));

        assertThat(result.getContent()).hasSize(1);
        assertThat(result.getContent().get(0).getUserId()).isEqualTo(userId);
    }

    @Test
    void getConversationMessages_found_returnsMessages() {
        UUID userId = UUID.randomUUID();
        UUID convId = UUID.randomUUID();
        Conversation conv = buildConversation(convId, userId, "Test");
        Message msg = buildMessage(convId, "user", "ÐŸÑ€Ð¸Ð²ÐµÑ‚");

        when(conversationRepository.findByIdAndUserId(convId, userId)).thenReturn(Optional.of(conv));
        when(messageRepository.findByConversationIdOrderByCreatedAtAsc(convId)).thenReturn(List.of(msg));

        List<Message> messages = chatService.getConversationMessages(convId, userId);

        assertThat(messages).hasSize(1);
        assertThat(messages.get(0).getContent()).isEqualTo("ÐŸÑ€Ð¸Ð²ÐµÑ‚");
    }

    @Test
    void getConversationMessages_notOwned_throwsResourceNotFound() {
        UUID userId = UUID.randomUUID();
        UUID convId = UUID.randomUUID();
        when(conversationRepository.findByIdAndUserId(convId, userId)).thenReturn(Optional.empty());

        assertThatThrownBy(() -> chatService.getConversationMessages(convId, userId)).isInstanceOf(
                ResourceNotFoundException.class);
    }

    @Test
    void addMessage_userRole_savedCorrectly() {
        UUID userId = UUID.randomUUID();
        UUID convId = UUID.randomUUID();
        Conversation conv = buildConversation(convId, userId, "Test");
        Message saved = buildMessage(convId, "user", "Ð‘Ð¾Ð»Ð¸Ñ‚ Ð³Ð¾Ð»Ð¾Ð²Ð°");

        when(conversationRepository.findByIdAndUserId(convId, userId)).thenReturn(Optional.of(conv));
        when(messageRepository.save(any())).thenReturn(saved);

        Message result = chatService.addMessage(convId, userId, "Ð‘Ð¾Ð»Ð¸Ñ‚ Ð³Ð¾Ð»Ð¾Ð²Ð°", true);

        assertThat(result.getRole()).isEqualTo("user");
        assertThat(result.getContent()).isEqualTo("Ð‘Ð¾Ð»Ð¸Ñ‚ Ð³Ð¾Ð»Ð¾Ð²Ð°");
    }

    @Test
    void addMessage_assistantRole_savedCorrectly() {
        UUID userId = UUID.randomUUID();
        UUID convId = UUID.randomUUID();
        Conversation conv = buildConversation(convId, userId, "Test");
        Message saved = buildMessage(convId, "assistant", "Ð ÐµÐºÐ¾Ð¼ÐµÐ½Ð´ÑƒÑŽ...");

        when(conversationRepository.findByIdAndUserId(convId, userId)).thenReturn(Optional.of(conv));
        when(messageRepository.save(any())).thenReturn(saved);

        Message result = chatService.addMessage(convId, userId, "Ð ÐµÐºÐ¾Ð¼ÐµÐ½Ð´ÑƒÑŽ...", false);

        assertThat(result.getRole()).isEqualTo("assistant");
    }

    @Test
    void addMessage_conversationNotOwned_throwsResourceNotFound() {
        UUID userId = UUID.randomUUID();
        UUID convId = UUID.randomUUID();
        when(conversationRepository.findByIdAndUserId(convId, userId)).thenReturn(Optional.empty());

        assertThatThrownBy(() -> chatService.addMessage(convId, userId, "text", true)).isInstanceOf(
                ResourceNotFoundException.class);
    }

    @Test
    void addAssistantMessage_withDrugReference_savedCorrectly() {
        UUID userId = UUID.randomUUID();
        UUID convId = UUID.randomUUID();
        UUID drugId = UUID.randomUUID();
        Conversation conv = buildConversation(convId, userId, "Test");

        when(conversationRepository.findByIdAndUserId(convId, userId)).thenReturn(Optional.of(conv));
        Message saved = Message.builder().id(UUID.randomUUID()).conversationId(convId).role("assistant").content(
                "ÐŸÐ¾Ð¿Ñ€Ð¾Ð±ÑƒÐ¹Ñ‚Ðµ ÐŸÐ°Ñ€Ð°Ñ†ÐµÑ‚Ð°Ð¼Ð¾Ð»").drugReference(drugId).ragSource("rag-doc-001").build();
        when(messageRepository.save(any())).thenReturn(saved);

        Message result = chatService.addAssistantMessage(
                convId,
                userId,
                "ÐŸÐ¾Ð¿Ñ€Ð¾Ð±ÑƒÐ¹Ñ‚Ðµ ÐŸÐ°Ñ€Ð°Ñ†ÐµÑ‚Ð°Ð¼Ð¾Ð»",
                drugId,
                "rag-doc-001");

        assertThat(result.getDrugReference()).isEqualTo(drugId);
        assertThat(result.getRagSource()).isEqualTo("rag-doc-001");
    }

    @Test
    void updateAnamnesisState_found_saves() {
        UUID convId = UUID.randomUUID();
        Conversation conv = buildConversation(UUID.randomUUID(), "Test");
        when(conversationRepository.findById(convId)).thenReturn(Optional.of(conv));
        when(conversationRepository.save(any())).thenReturn(conv);

        Map<String, Object> state = Map.of("stage", "collecting", "symptoms", List.of("headache"));
        chatService.updateConversationAnamnesisState(convId, state);

        verify(conversationRepository).save(argThat(c -> "collecting".equals(c.getAnamnesisState().get("stage"))));
    }

    @Test
    void updateAnamnesisState_notFound_throwsResourceNotFound() {
        UUID convId = UUID.randomUUID();
        when(conversationRepository.findById(convId)).thenReturn(Optional.empty());

        assertThatThrownBy(() -> chatService.updateConversationAnamnesisState(convId, Map.of())).isInstanceOf(
                ResourceNotFoundException.class);
    }

    @Test
    void deleteConversation_owned_deletesSuccessfully() {
        UUID userId = UUID.randomUUID();
        UUID convId = UUID.randomUUID();
        Conversation conv = buildConversation(convId, userId, "Test");
        when(conversationRepository.findByIdAndUserId(convId, userId)).thenReturn(Optional.of(conv));

        chatService.deleteConversation(convId, userId);

        verify(conversationRepository).delete(conv);
    }

    @Test
    void deleteConversation_notOwned_throwsResourceNotFound() {
        UUID userId = UUID.randomUUID();
        UUID convId = UUID.randomUUID();
        when(conversationRepository.findByIdAndUserId(convId, userId)).thenReturn(Optional.empty());

        assertThatThrownBy(() -> chatService.deleteConversation(convId, userId)).isInstanceOf(
                ResourceNotFoundException.class);
    }

    @Test
    void getRecentMessages_limitsResults() {
        UUID convId = UUID.randomUUID();
        List<Message> allMessages = List.of(
                buildMessage(convId, "user", "msg1"),
                buildMessage(convId, "assistant", "msg2"),
                buildMessage(convId, "user", "msg3"),
                buildMessage(convId, "assistant", "msg4"),
                buildMessage(convId, "user", "msg5"));
        when(messageRepository.findByConversationIdOrderByCreatedAtDesc(convId)).thenReturn(allMessages);

        List<Message> recent = chatService.getRecentMessages(convId, 3);

        assertThat(recent).hasSize(3);
    }

    private Conversation buildConversation(UUID userId, String title) {
        return buildConversation(UUID.randomUUID(), userId, title);
    }

    private Conversation buildConversation(UUID convId, UUID userId, String title) {
        return Conversation.builder().id(convId).userId(userId).title(title).status("active").build();
    }

    private Message buildMessage(UUID convId, String role, String content) {
        return Message.builder().id(UUID.randomUUID()).conversationId(convId).role(role).content(content).build();
    }
}