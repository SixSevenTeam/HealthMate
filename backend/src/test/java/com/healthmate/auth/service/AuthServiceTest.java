package com.healthmate.auth.service;

import com.healthmate.auth.dto.LoginRequest;
import com.healthmate.auth.dto.RegisterRequest;
import com.healthmate.auth.dto.UserResponse;
import com.healthmate.auth.entity.User;
import com.healthmate.auth.repository.UserRepository;
import com.healthmate.exception.EmailAlreadyExistsException;
import com.healthmate.exception.ResourceNotFoundException;
import com.healthmate.medications.service.MedicationsService;
import com.healthmate.profile.dto.MedicalProfileRequest;
import com.healthmate.profile.service.ProfileService;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.security.authentication.BadCredentialsException;
import org.springframework.security.crypto.password.PasswordEncoder;

import java.time.Instant;
import java.time.LocalDate;
import java.util.Optional;
import java.util.UUID;

import static org.assertj.core.api.Assertions.*;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

@ExtendWith(MockitoExtension.class)
class AuthServiceTest {

    @Mock UserRepository userRepository;
    @Mock PasswordEncoder passwordEncoder;
    @Mock JwtTokenProvider jwtTokenProvider;
    @Mock ProfileService profileService;
    @Mock MedicationsService medicationsService;

    AuthService authService;

    @BeforeEach
    void setUp() {
        authService = new AuthService(
                userRepository, passwordEncoder, jwtTokenProvider, profileService, medicationsService
        );
    }


    @Test
    void register_success_returnsUserResponse() {
        RegisterRequest req = buildRegisterRequest("new@mail.com");

        when(userRepository.existsByEmail("new@mail.com")).thenReturn(false);
        when(passwordEncoder.encode("password123")).thenReturn("hashed");
        when(userRepository.save(any())).thenAnswer(inv -> {
            User u = inv.getArgument(0);
            u = User.builder()
                    .id(UUID.randomUUID())
                    .email(u.getEmail())
                    .firstName(u.getFirstName())
                    .lastName(u.getLastName())
                    .birthDate(u.getBirthDate())
                    .passwordHash(u.getPasswordHash())
                    .isActive(true)
                    .build();
            return u;
        });
        when(profileService.updateProfile(any(), any(MedicalProfileRequest.class)))
                .thenReturn(Instant.now());

        UserResponse result = authService.register(req);

        assertThat(result.getEmail()).isEqualTo("new@mail.com");
        assertThat(result.getFirstName()).isEqualTo("Ivan");
        verify(userRepository).save(any());
        verify(profileService).updateProfile(any(), any());
    }

    @Test
    void register_duplicateEmail_throwsEmailAlreadyExists() {
        RegisterRequest req = buildRegisterRequest("dup@mail.com");
        when(userRepository.existsByEmail("dup@mail.com")).thenReturn(true);

        assertThatThrownBy(() -> authService.register(req))
                .isInstanceOf(EmailAlreadyExistsException.class)
                .hasMessageContaining("dup@mail.com");
    }


    @Test
    void login_validCredentials_returnsLoginResult() {
        User user = buildUser("test@mail.com", "hashed");
        when(userRepository.findByEmail("test@mail.com")).thenReturn(Optional.of(user));
        when(passwordEncoder.matches("password123", "hashed")).thenReturn(true);
        when(jwtTokenProvider.generateToken(user.getId())).thenReturn("jwt-token");

        AuthService.LoginResult result = authService.login(new LoginRequest("test@mail.com", "password123"));

        assertThat(result.token()).isEqualTo("jwt-token");
        assertThat(result.user().getEmail()).isEqualTo("test@mail.com");
    }

    @Test
    void login_userNotFound_throwsBadCredentials() {
        when(userRepository.findByEmail("ghost@mail.com")).thenReturn(Optional.empty());

        assertThatThrownBy(() -> authService.login(new LoginRequest("ghost@mail.com", "pass")))
                .isInstanceOf(BadCredentialsException.class);
    }

    @Test
    void login_wrongPassword_throwsBadCredentials() {
        User user = buildUser("test@mail.com", "hashed");
        when(userRepository.findByEmail("test@mail.com")).thenReturn(Optional.of(user));
        when(passwordEncoder.matches("wrong", "hashed")).thenReturn(false);

        assertThatThrownBy(() -> authService.login(new LoginRequest("test@mail.com", "wrong")))
                .isInstanceOf(BadCredentialsException.class);
    }

    @Test
    void login_inactiveUser_throwsIllegalState() {
        User user = User.builder()
                .id(UUID.randomUUID())
                .email("inactive@mail.com")
                .passwordHash("hashed")
                .isActive(false)
                .build();
        when(userRepository.findByEmail("inactive@mail.com")).thenReturn(Optional.of(user));

        assertThatThrownBy(() -> authService.login(new LoginRequest("inactive@mail.com", "pass")))
                .isInstanceOf(IllegalStateException.class);
    }


    @Test
    void getCurrentUser_found_returnsResponse() {
        UUID userId = UUID.randomUUID();
        User user = buildUser("me@mail.com", "hashed");

        when(userRepository.findById(userId)).thenReturn(Optional.of(user));

        UserResponse response = authService.getCurrentUser(userId);
        assertThat(response.getEmail()).isEqualTo("me@mail.com");
    }

    @Test
    void getCurrentUser_notFound_throwsResourceNotFound() {
        UUID userId = UUID.randomUUID();
        when(userRepository.findById(userId)).thenReturn(Optional.empty());

        assertThatThrownBy(() -> authService.getCurrentUser(userId))
                .isInstanceOf(ResourceNotFoundException.class);
    }


    private RegisterRequest buildRegisterRequest(String email) {
        RegisterRequest req = new RegisterRequest();
        req.setEmail(email);
        req.setPassword("password123");
        req.setFirstName("Ivan");
        req.setLastName("Ivanov");
        req.setBirthDate(LocalDate.of(1990, 6, 15));
        return req;
    }

    private User buildUser(String email, String passwordHash) {
        return User.builder()
                .id(UUID.randomUUID())
                .email(email)
                .passwordHash(passwordHash)
                .firstName("Ivan")
                .lastName("Ivanov")
                .birthDate(LocalDate.of(1990, 6, 15))
                .isActive(true)
                .build();
    }
}
