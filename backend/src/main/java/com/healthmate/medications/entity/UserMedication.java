package com.healthmate.medications.entity;

import jakarta.persistence.*;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;
import org.hibernate.annotations.CreationTimestamp;
import org.hibernate.annotations.UpdateTimestamp;

import java.math.BigDecimal;
import java.time.Instant;
import java.time.LocalDate;
import java.util.UUID;

@Entity
@Table(name = "user_medications", schema = "medications")
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class UserMedication {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    private UUID id;

    @Column(nullable = false)
    private UUID userId;

    @Column(name = "drug_id")
    private UUID drugId;

    @Column(name = "custom_name")
    private String customName;

    @Column(name = "dose_amount", nullable = false)
    private BigDecimal doseAmount;

    @Column(name = "dose_unit", nullable = false)
    private String doseUnit;

    @Column(name = "instructions", columnDefinition = "TEXT")
    private String instructions;

    @Column(name = "start_date")
    private LocalDate startDate;

    @Column(name = "end_date")
    private LocalDate endDate;

    @Column(nullable = false)
    @Builder.Default
    private Boolean isActive = true;

    @CreationTimestamp
    @Column(nullable = false, updatable = false)
    private Instant createdAt;

    @UpdateTimestamp
    @Column(nullable = false)
    private Instant updatedAt;
}
