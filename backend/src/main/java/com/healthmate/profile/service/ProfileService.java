package com.healthmate.profile.service;

import com.healthmate.common.encryption.EncryptionService;
import com.healthmate.profile.dto.AllergyDTO;
import com.healthmate.profile.dto.DiagnosisDTO;
import com.healthmate.profile.dto.MedicalProfileRequest;
import com.healthmate.profile.dto.MedicalProfileResponse;
import com.healthmate.profile.entity.MedicalProfile;
import com.healthmate.profile.repository.MedicalProfileRepository;
import com.healthmate.exception.ResourceNotFoundException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.core.type.TypeReference;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.time.Instant;
import java.util.UUID;

@Slf4j
@Service
public class ProfileService {

    private final MedicalProfileRepository profileRepository;
    private final EncryptionService encryptionService;
    private final ObjectMapper objectMapper = new ObjectMapper();

    public ProfileService(MedicalProfileRepository profileRepository, EncryptionService encryptionService) {
        this.profileRepository = profileRepository;
        this.encryptionService = encryptionService;
    }

    public MedicalProfileResponse getProfile(UUID userId) {
        MedicalProfile profile = profileRepository.findByUserId(userId)
            .orElseThrow(() -> new ResourceNotFoundException("Medical profile not found for user"));

        return mapToResponse(profile);
    }

    @Transactional
    public Instant updateProfile(UUID userId, MedicalProfileRequest request) {
        MedicalProfile profile = profileRepository.findByUserId(userId)
            .orElse(MedicalProfile.builder()
                .userId(userId)
                .build());

        profile.setHeightCm(request.getHeightCm());
        profile.setWeightKg(request.getWeightKg());
        profile.setBloodType(request.getBloodType());

        // Encrypt sensitive data
        if (request.getDiagnoses() != null) {
            String diagnosesJson = serializeToJson(request.getDiagnoses());
            profile.setDiagnoses(encryptionService.encrypt(diagnosesJson));
        }

        if (request.getAllergies() != null) {
            String allergiesJson = serializeToJson(request.getAllergies());
            profile.setAllergies(encryptionService.encrypt(allergiesJson));
        }

        MedicalProfile saved = profileRepository.save(profile);
        log.info("Profile updated for user: {}", userId);
        return saved.getUpdatedAt();
    }

    public UserContextDTO getUserContext(UUID userId) {
        MedicalProfile profile = profileRepository.findByUserId(userId)
            .orElse(MedicalProfile.builder()
                .userId(userId)
                .diagnoses(encryptionService.encrypt("[]"))
                .allergies(encryptionService.encrypt("[]"))
                .build());

        List<String> contextWarnings = new ArrayList<>();

        return UserContextDTO.builder()
            .userId(userId)
            .heightCm(profile.getHeightCm())
            .weightKg(profile.getWeightKg())
            .bloodType(profile.getBloodType())
            .diagnoses(deserializeDiagnoses(profile.getDiagnoses(), contextWarnings))
            .allergies(deserializeAllergies(profile.getAllergies(), contextWarnings))
            .contextDegraded(!contextWarnings.isEmpty())
            .contextWarnings(contextWarnings)
            .activeMedications(Collections.emptyList())
            .build();
    }

    private MedicalProfileResponse mapToResponse(MedicalProfile profile) {
        return MedicalProfileResponse.builder()
            .heightCm(profile.getHeightCm())
            .weightKg(profile.getWeightKg())
            .bloodType(profile.getBloodType())
            .diagnoses(deserializeDiagnoses(profile.getDiagnoses()))
            .allergies(deserializeAllergies(profile.getAllergies()))
            .updatedAt(profile.getUpdatedAt())
            .build();
    }

    private List<DiagnosisDTO> deserializeDiagnoses(String encrypted) {
        return deserializeDiagnoses(encrypted, null);
    }

    private List<DiagnosisDTO> deserializeDiagnoses(String encrypted, List<String> warningsCollector) {
        String decrypted = encryptionService.decrypt(encrypted);
        try {
            return objectMapper.readValue(decrypted, new TypeReference<List<DiagnosisDTO>>() {});
        } catch (Exception e) {
            log.warn("Failed to parse diagnoses for profile context", e);
            if (warningsCollector != null) {
                warningsCollector.add("Failed to parse diagnoses from encrypted profile");
            }
            return Collections.emptyList();
        }
    }

    private List<AllergyDTO> deserializeAllergies(String encrypted) {
        return deserializeAllergies(encrypted, null);
    }

    private List<AllergyDTO> deserializeAllergies(String encrypted, List<String> warningsCollector) {
        String decrypted = encryptionService.decrypt(encrypted);
        try {
            return objectMapper.readValue(decrypted, new TypeReference<List<AllergyDTO>>() {});
        } catch (Exception e) {
            log.warn("Failed to parse allergies for profile context", e);
            if (warningsCollector != null) {
                warningsCollector.add("Failed to parse allergies from encrypted profile");
            }
            return Collections.emptyList();
        }
    }

    private String serializeToJson(Object obj) {
        try {
            return objectMapper.writeValueAsString(obj);
        } catch (Exception e) {
            return "[]";
        }
    }
}
