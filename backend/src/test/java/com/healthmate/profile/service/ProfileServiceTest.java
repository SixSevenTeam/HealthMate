package com.healthmate.profile.service;


import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.argThat;
import static org.mockito.Mockito.atLeastOnce;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.List;
import java.util.Optional;
import java.util.UUID;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import com.healthmate.common.encryption.EncryptionService;
import com.healthmate.exception.ResourceNotFoundException;
import com.healthmate.profile.dto.AllergyDTO;
import com.healthmate.profile.dto.DiagnosisDTO;
import com.healthmate.profile.dto.MedicalProfileRequest;
import com.healthmate.profile.dto.MedicalProfileResponse;
import com.healthmate.profile.entity.MedicalProfile;
import com.healthmate.profile.repository.MedicalProfileRepository;


@ExtendWith(MockitoExtension.class)
class ProfileServiceTest {

    @Mock
    MedicalProfileRepository profileRepository;
    @Mock
    EncryptionService encryptionService;

    ProfileService profileService;

    @BeforeEach
    void setUp() {
        profileService = new ProfileService(profileRepository, encryptionService);
    }

    @Test
    void getProfile_exists_returnsResponse() {
        UUID userId = UUID.randomUUID();
        MedicalProfile profile = buildProfile(userId);

        when(profileRepository.findByUserId(userId)).thenReturn(Optional.of(profile));
        when(encryptionService.decrypt("[]")).thenReturn("[]");

        MedicalProfileResponse response = profileService.getProfile(userId);

        assertThat(response.getHeightCm()).isEqualTo(175);
        assertThat(response.getBloodType()).isEqualTo("A+");
        assertThat(response.getWeightKg()).isEqualByComparingTo("70.0");
    }

    @Test
    void getProfile_notFound_throwsResourceNotFound() {
        UUID userId = UUID.randomUUID();
        when(profileRepository.findByUserId(userId)).thenReturn(Optional.empty());

        assertThatThrownBy(() -> profileService.getProfile(userId)).isInstanceOf(ResourceNotFoundException.class);
    }

    @Test
    void getProfile_diagnosesParsed() {
        UUID userId = UUID.randomUUID();
        MedicalProfile profile = buildProfile(userId);

        when(profileRepository.findByUserId(userId)).thenReturn(Optional.of(profile));
        when(encryptionService.decrypt("[]")).thenReturn("[]");

        MedicalProfileResponse response = profileService.getProfile(userId);

        assertThat(response.getDiagnoses()).isNotNull();
        assertThat(response.getAllergies()).isNotNull();
    }

    @Test
    void updateProfile_newProfile_savesAndReturnsTimestamp() {
        UUID userId = UUID.randomUUID();
        MedicalProfileRequest request = buildRequest();

        when(profileRepository.findByUserId(userId)).thenReturn(Optional.empty());
        when(encryptionService.encrypt(any())).thenReturn("encrypted_data");
        MedicalProfile saved = buildProfile(userId);
        when(profileRepository.save(any())).thenReturn(saved);

        Instant result = profileService.updateProfile(userId, request);

        assertThat(result).isNotNull();
        verify(profileRepository).save(any());
        verify(encryptionService, atLeastOnce()).encrypt(any());
    }

    @Test
    void updateProfile_existingProfile_updatesFields() {
        UUID userId = UUID.randomUUID();
        MedicalProfile existing = buildProfile(userId);
        MedicalProfileRequest request = buildRequest();
        request.setHeightCm(190);

        when(profileRepository.findByUserId(userId)).thenReturn(Optional.of(existing));
        when(encryptionService.encrypt(any())).thenReturn("encrypted_data");
        when(profileRepository.save(any())).thenAnswer(inv -> {
            MedicalProfile p = inv.getArgument(0);
            return p;
        });

        profileService.updateProfile(userId, request);

        verify(profileRepository).save(argThat(p -> p.getHeightCm() == 190));
    }

    @Test
    void updateProfile_nullDiagnoses_doesNotEncrypt() {
        UUID userId = UUID.randomUUID();
        MedicalProfileRequest request = new MedicalProfileRequest();
        request.setHeightCm(170);

        when(profileRepository.findByUserId(userId)).thenReturn(Optional.empty());
        MedicalProfile saved = buildProfile(userId);
        when(profileRepository.save(any())).thenReturn(saved);

        profileService.updateProfile(userId, request);

        verify(encryptionService, never()).encrypt(any());
    }

    @Test
    void getUserContext_profileExists_returnsContext() {
        UUID userId = UUID.randomUUID();
        MedicalProfile profile = buildProfile(userId);

        when(profileRepository.findByUserId(userId)).thenReturn(Optional.of(profile));
        when(encryptionService.decrypt("[]")).thenReturn("[]");

        UserContextDTO ctx = profileService.getUserContext(userId);

        assertThat(ctx.getUserId()).isEqualTo(userId);
        assertThat(ctx.getHeightCm()).isEqualTo(175);
        assertThat(ctx.getBloodType()).isEqualTo("A+");
        assertThat(ctx.getActiveMedications()).isEmpty();
    }

    @Test
    void getUserContext_noProfile_returnsEmptyContext() {
        UUID userId = UUID.randomUUID();
        when(profileRepository.findByUserId(userId)).thenReturn(Optional.empty());
        when(encryptionService.encrypt("[]")).thenReturn("encrypted_empty");
        when(encryptionService.decrypt("encrypted_empty")).thenReturn("[]");

        UserContextDTO ctx = profileService.getUserContext(userId);

        assertThat(ctx.getUserId()).isEqualTo(userId);
        assertThat(ctx.getDiagnoses()).isEmpty();
        assertThat(ctx.getAllergies()).isEmpty();
    }

    @Test
    void getUserContext_corruptedData_degradesGracefully() {
        UUID userId = UUID.randomUUID();
        MedicalProfile profile = MedicalProfile.builder().userId(userId).diagnoses("corrupted_base64_garbage")
                .allergies("also_corrupted").updatedAt(Instant.now()).build();

        when(profileRepository.findByUserId(userId)).thenReturn(Optional.of(profile));
        when(encryptionService.decrypt("corrupted_base64_garbage")).thenReturn("not_valid_json{{");
        when(encryptionService.decrypt("also_corrupted")).thenReturn("not_valid_json{{");

        UserContextDTO ctx = profileService.getUserContext(userId);

        assertThat(ctx.getDiagnoses()).isEmpty();
        assertThat(ctx.getAllergies()).isEmpty();
        assertThat(ctx.getContextDegraded()).isTrue();
    }

    private MedicalProfile buildProfile(UUID userId) {
        return MedicalProfile.builder().id(UUID.randomUUID()).userId(userId).heightCm(175).weightKg(
                BigDecimal.valueOf(70)).bloodType("A+").diagnoses("[]").allergies("[]").updatedAt(Instant.now())
                .build();
    }

    private MedicalProfileRequest buildRequest() {
        MedicalProfileRequest req = new MedicalProfileRequest();
        req.setHeightCm(175);
        req.setWeightKg(BigDecimal.valueOf(70));
        req.setBloodType("A+");
        req.setDiagnoses(List.of(new DiagnosisDTO("Ð“Ð¸Ð¿ÐµÑ€Ñ‚Ð¾Ð½Ð¸Ñ", null)));
        req.setAllergies(List.of(new AllergyDTO("Ð¿ÐµÐ½Ð¸Ñ†Ð¸Ð»Ð»Ð¸Ð½", "ÑÑ‹Ð¿ÑŒ")));
        return req;
    }
}
