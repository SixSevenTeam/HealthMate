package com.healthmate.profile.entity;

import jakarta.persistence.*;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;
import org.hibernate.annotations.UpdateTimestamp;

import java.time.Instant;
import java.util.UUID;

@Entity
@Table(name = "medical_profiles", schema = "profile")
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class MedicalProfile {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    private UUID id;

    @Column(nullable = false, unique = true)
    private UUID userId;

    @Column(name = "height_cm")
    private Integer heightCm;

    @Column(name = "weight_kg")
    private java.math.BigDecimal weightKg;

    @Column(name = "blood_type")
    private String bloodType;

    @Column(nullable = false)
    @Builder.Default
    private String diagnoses = "[]";

    @Column(nullable = false)
    @Builder.Default
    private String allergies = "[]";

    @UpdateTimestamp
    @Column(nullable = false)
    private Instant updatedAt;
}
