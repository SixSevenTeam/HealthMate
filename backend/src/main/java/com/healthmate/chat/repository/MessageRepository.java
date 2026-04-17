package com.healthmate.chat.repository;

import com.healthmate.chat.entity.Message;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

@Repository
public interface MessageRepository extends JpaRepository<Message, UUID> {
    List<Message> findByConversationIdOrderByCreatedAtDesc(UUID conversationId);
    List<Message> findByConversationIdOrderByCreatedAtAsc(UUID conversationId);
}
