package com.healthmate.profile.repository;

import com.healthmate.profile.entity.MedicalProfile;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.Optional;
import java.util.UUID;

@Repository
public interface MedicalProfileRepository extends JpaRepository<MedicalProfile, UUID> {
    Optional<MedicalProfile> findByUserId(UUID userId);
}
