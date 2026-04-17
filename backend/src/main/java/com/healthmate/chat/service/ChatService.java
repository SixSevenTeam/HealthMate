package com.healthmate.chat.service;

import com.healthmate.chat.entity.Conversation;
import com.healthmate.chat.entity.Message;
import com.healthmate.chat.repository.ConversationRepository;
import com.healthmate.chat.repository.MessageRepository;
import com.healthmate.exception.ResourceNotFoundException;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.Map;
import java.util.UUID;

@Slf4j
@Service
public class ChatService {

    private final ConversationRepository conversationRepository;
    private final MessageRepository messageRepository;

    public ChatService(ConversationRepository conversationRepository, MessageRepository messageRepository) {
        this.conversationRepository = conversationRepository;
        this.messageRepository = messageRepository;
    }

    @Transactional
    public Conversation createConversation(UUID userId, String title) {
        Conversation conversation = Conversation.builder()
            .userId(userId)
            .title(title != null ? title : "New Conversation")
            .status("active")
            .anamnesisState(null)
            .build();

        Conversation saved = conversationRepository.save(conversation);
        log.info("Conversation created: {}", saved.getId());
        return saved;
    }

    public Page<Conversation> getUserConversations(UUID userId, Pageable pageable) {
        return conversationRepository.findByUserId(userId, pageable);
    }

    public List<Message> getConversationMessages(UUID conversationId, UUID userId) {
        Conversation conversation = conversationRepository.findByIdAndUserId(conversationId, userId)
            .orElseThrow(() -> new ResourceNotFoundException("Conversation not found"));

        return messageRepository.findByConversationIdOrderByCreatedAtAsc(conversationId);
    }

    @Transactional
    public Message addMessage(UUID conversationId, UUID userId, String content, boolean isUser) {
        Conversation conversation = conversationRepository.findByIdAndUserId(conversationId, userId)
            .orElseThrow(() -> new ResourceNotFoundException("Conversation not found"));

        Message message = Message.builder()
            .conversationId(conversationId)
            .role(isUser ? "user" : "assistant")
            .content(content)
            .build();

        Message saved = messageRepository.save(message);
        log.info("Message added to conversation: {}", conversationId);
        return saved;
    }

    @Transactional
    public void updateConversationAnamnesisState(UUID conversationId, Map<String, Object> anamnesisState) {
        Conversation conversation = conversationRepository.findById(conversationId)
            .orElseThrow(() -> new ResourceNotFoundException("Conversation not found"));

        conversation.setAnamnesisState(anamnesisState);
        conversationRepository.save(conversation);
    }

    public Map<String, Object> getAnamnesisState(UUID conversationId) {
        Conversation conversation = conversationRepository.findById(conversationId)
            .orElseThrow(() -> new ResourceNotFoundException("Conversation not found"));

        return conversation.getAnamnesisState();
    }

    @Transactional
    public void deleteConversation(UUID conversationId, UUID userId) {
        Conversation conversation = conversationRepository.findByIdAndUserId(conversationId, userId)
            .orElseThrow(() -> new ResourceNotFoundException("Conversation not found"));

        conversationRepository.delete(conversation);
        log.info("Conversation deleted: {}", conversationId);
    }

    public List<Message> getRecentMessages(UUID conversationId, int limit) {
        List<Message> allMessages = messageRepository.findByConversationIdOrderByCreatedAtDesc(conversationId);
        return allMessages.stream().limit(limit).toList();
    }

    public Conversation getConversation(UUID conversationId, UUID userId) {
        return conversationRepository.findByIdAndUserId(conversationId, userId)
            .orElseThrow(() -> new ResourceNotFoundException("Conversation not found"));
    }

    @Transactional
    public Message addAssistantMessage(
        UUID conversationId,
        UUID userId,
        String content,
        UUID drugReference,
        String ragSource
    ) {
        conversationRepository.findByIdAndUserId(conversationId, userId)
            .orElseThrow(() -> new ResourceNotFoundException("Conversation not found"));

        Message message = Message.builder()
            .conversationId(conversationId)
            .role("assistant")
            .content(content)
            .drugReference(drugReference)
            .ragSource(ragSource)
            .build();

        Message saved = messageRepository.save(message);
        log.info("Assistant message added to conversation: {}", conversationId);
        return saved;
    }
}
