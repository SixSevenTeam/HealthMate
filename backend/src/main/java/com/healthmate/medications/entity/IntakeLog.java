package com.healthmate.medications.entity;

import jakarta.persistence.*;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;
import org.hibernate.annotations.CreationTimestamp;

import java.time.Instant;
import java.util.UUID;

@Entity
@Table(name = "intake_logs", schema = "medications")
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class IntakeLog {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    private UUID id;

    @Column(name = "user_medication_id", nullable = false)
    private UUID userMedicationId;

    @Column(name = "scheduled_at", nullable = false)
    private Instant scheduledAt;

    @Column(name = "taken_at")
    private Instant takenAt;

    @Column(nullable = false)
    @Builder.Default
    private String status = "pending";

    @Column(name = "confirmed_via")
    private String confirmedVia;

    @CreationTimestamp
    @Column(nullable = false, updatable = false)
    private Instant createdAt;
}
