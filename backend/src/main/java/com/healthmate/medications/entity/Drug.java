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
import java.util.UUID;

@Entity
@Table(name = "drugs", schema = "medications")
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class Drug {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    private UUID id;

    @Column(name = "trade_name", nullable = false, length = 255)
    private String tradeName;

    @Column(name = "international_name", length = 255)
    private String internationalName;

    @Column(name = "atx_code", length = 20)
    private String atxCode;

    @Column(name = "min_dose")
    private BigDecimal minDose;

    @Column(name = "max_dose")
    private BigDecimal maxDose;

    @Column(name = "dose_unit", length = 20)
    private String doseUnit;

    @Column(name = "is_in_rag")
    @Builder.Default
    private Boolean isInRag = false;

    @CreationTimestamp
    @Column(nullable = false, updatable = false)
    private Instant createdAt;

    @UpdateTimestamp
    @Column(nullable = false)
    private Instant updatedAt;
}
