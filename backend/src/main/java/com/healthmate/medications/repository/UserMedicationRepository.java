package com.healthmate.medications.repository;

import com.healthmate.medications.entity.UserMedication;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

@Repository
public interface UserMedicationRepository extends JpaRepository<UserMedication, UUID> {
    @Query("SELECT m FROM UserMedication m WHERE m.userId = ?1 ORDER BY m.createdAt DESC")
    Page<UserMedication> findByUserId(UUID userId, Pageable pageable);
    List<UserMedication> findByUserIdAndIsActive(UUID userId, Boolean isActive);
    Optional<UserMedication> findByIdAndUserId(UUID id, UUID userId);
}
