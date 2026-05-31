package com.healthmate.auth.service;

import com.healthmate.auth.dto.LoginRequest;
import com.healthmate.auth.dto.RegisterRequest;
import com.healthmate.auth.dto.UserResponse;
import com.healthmate.auth.entity.User;
import com.healthmate.auth.repository.UserRepository;
import com.healthmate.exception.EmailAlreadyExistsException;
import com.healthmate.exception.ResourceNotFoundException;
import com.healthmate.medications.entity.UserMedication;
import com.healthmate.medications.service.MedicationsService;
import com.healthmate.profile.dto.MedicalProfileRequest;
import com.healthmate.profile.service.ProfileService;
import lombok.extern.slf4j.Slf4j;
import org.springframework.security.authentication.BadCredentialsException;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.UUID;

@Slf4j
@Service
public class AuthService {

    private final UserRepository userRepository;
    private final PasswordEncoder passwordEncoder;
    private final JwtTokenProvider jwtTokenProvider;
    private final ProfileService profileService;
    private final MedicationsService medicationsService;

    public AuthService(
        UserRepository userRepository,
        PasswordEncoder passwordEncoder,
        JwtTokenProvider jwtTokenProvider,
        ProfileService profileService,
        MedicationsService medicationsService
    ) {
        this.userRepository = userRepository;
        this.passwordEncoder = passwordEncoder;
        this.jwtTokenProvider = jwtTokenProvider;
        this.profileService = profileService;
        this.medicationsService = medicationsService;
    }

    @Transactional
    public UserResponse register(RegisterRequest request) {
        if (userRepository.existsByEmail(request.getEmail())) {
            throw new EmailAlreadyExistsException("Email " + request.getEmail() + " is already registered");
        }

        User user = User.builder()
            .email(request.getEmail())
            .passwordHash(passwordEncoder.encode(request.getPassword()))
            .firstName(request.getFirstName())
            .lastName(request.getLastName())
            .birthDate(request.getBirthDate())
            .isActive(true)
            .build();

        user = userRepository.save(user);
        profileService.updateProfile(user.getId(), buildMedicalProfileRequest(request));
        saveInitialMedications(user.getId(), request);
        log.info("New user registered: {}", user.getEmail());

        return mapToResponse(user);
    }

    public LoginResult login(LoginRequest request) {
        User user = userRepository.findByEmail(request.getEmail())
            .orElseThrow(() -> new BadCredentialsException("Invalid credentials"));

        if (!user.getIsActive()) {
            throw new IllegalStateException("Account is inactive");
        }

        if (!passwordEncoder.matches(request.getPassword(), user.getPasswordHash())) {
            throw new BadCredentialsException("Invalid credentials");
        }

        log.info("User logged in: {}", user.getEmail());
        return new LoginResult(jwtTokenProvider.generateToken(user.getId()), mapToResponse(user));
    }

    public UserResponse getCurrentUser(UUID userId) {
        User user = userRepository.findById(userId)
            .orElseThrow(() -> new ResourceNotFoundException("User not found"));

        return mapToResponse(user);
    }

    public User getUserEntity(UUID userId) {
        return userRepository.findById(userId)
            .orElseThrow(() -> new ResourceNotFoundException("User not found"));
    }

    private UserResponse mapToResponse(User user) {
        return new UserResponse(
            user.getId(),
            user.getEmail(),
            user.getFirstName(),
            user.getLastName(),
            user.getBirthDate()
        );
    }

    private MedicalProfileRequest buildMedicalProfileRequest(RegisterRequest request) {
        MedicalProfileRequest profileRequest = new MedicalProfileRequest();
        profileRequest.setHeightCm(request.getHeightCm());
        profileRequest.setWeightKg(request.getWeightKg());
        profileRequest.setBloodType(request.getBloodType());
        profileRequest.setDiagnoses(request.getDiagnoses());
        profileRequest.setAllergies(request.getAllergies());
        return profileRequest;
    }

    private void saveInitialMedications(UUID userId, RegisterRequest request) {
        if (request.getInitialMedications() == null || request.getInitialMedications().isEmpty()) {
            return;
        }

        for (RegisterRequest.InitialMedicationDTO item : request.getInitialMedications()) {
            if (item.getDrugId() == null && (item.getCustomName() == null || item.getCustomName().isBlank())) {
                throw new IllegalArgumentException("Initial medication must include drugId or customName");
            }

            UserMedication medication = UserMedication.builder()
                .drugId(item.getDrugId())
                .customName(item.getCustomName())
                .doseAmount(item.getDoseAmount())
                .doseUnit(item.getDoseUnit())
                .instructions(item.getInstructions())
                .startDate(item.getStartDate())
                .endDate(item.getEndDate())
                .isActive(true)
                .build();

            medicationsService.addUserMedication(userId, medication);
        }
    }

    public record LoginResult(String token, UserResponse user) {}
}
