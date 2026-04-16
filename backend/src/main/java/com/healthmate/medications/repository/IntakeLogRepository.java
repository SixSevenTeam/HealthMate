package com.healthmate.medications.repository;

import com.healthmate.medications.entity.IntakeLog;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.time.Instant;
import java.util.List;
import java.util.UUID;

@Repository
public interface IntakeLogRepository extends JpaRepository<IntakeLog, UUID> {
    List<IntakeLog> findByUserMedicationIdAndScheduledAtBetween(
        UUID userMedicationId, Instant from, Instant to);
    List<IntakeLog> findByUserMedicationIdInAndScheduledAtGreaterThanEqualAndScheduledAtLessThan(
        List<UUID> userMedicationIds,
        Instant from,
        Instant to
    );
    List<IntakeLog> findByUserMedicationIdAndScheduledAtGreaterThan(UUID userMedicationId, Instant after);
    void deleteByUserMedicationIdAndStatusAndScheduledAtGreaterThan(
        UUID userMedicationId,
        String status,
        Instant after
    );
}
