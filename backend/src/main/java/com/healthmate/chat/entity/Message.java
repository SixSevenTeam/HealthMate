package com.healthmate.chat.entity;

import jakarta.persistence.*;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;
import org.hibernate.annotations.CreationTimestamp;

import java.time.Instant;
import java.util.UUID;

@Entity
@Table(name = "messages", schema = "chat")
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class Message {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    private UUID id;

    @Column(name = "conversation_id", nullable = false)
    private UUID conversationId;

    @Column(nullable = false, length = 20)
    private String role; // user or assistant

    @Column(nullable = false, columnDefinition = "TEXT")
    private String content;

    @Column(name = "drug_reference")
    private UUID drugReference;

    @Column(name = "rag_source")
    private String ragSource;

    @CreationTimestamp
    @Column(nullable = false, updatable = false)
    private Instant createdAt;
}
