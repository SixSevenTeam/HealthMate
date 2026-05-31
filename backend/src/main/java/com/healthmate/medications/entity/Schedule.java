package com.healthmate.medications.entity;

import jakarta.persistence.*;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;
import org.hibernate.annotations.CreationTimestamp;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

import java.time.Instant;
import java.time.LocalTime;
import java.util.UUID;

@Entity
@Table(name = "schedules", schema = "medications")
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class Schedule {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    private UUID id;

    @Column(name = "user_medication_id", nullable = false)
    private UUID userMedicationId;

    @Column(name = "time_of_day", nullable = false)
    private LocalTime timeOfDay;

    @Column(name = "days_of_week", columnDefinition = "integer[]", nullable = false)
    @JdbcTypeCode(SqlTypes.ARRAY)
    private Integer[] daysOfWeek;

    @CreationTimestamp
    @Column(nullable = false, updatable = false)
    private Instant createdAt;
}
