package com.healthmate.auth.service;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.test.util.ReflectionTestUtils;

import java.util.UUID;

import static org.assertj.core.api.Assertions.*;

class JwtTokenProviderTest {

    JwtTokenProvider provider;

    @BeforeEach
    void setUp() {
        provider = new JwtTokenProvider();
        ReflectionTestUtils.setField(provider, "jwtSecret",
                "healthmate_test_secret_key_min_32_chars_long!!");
        ReflectionTestUtils.setField(provider, "jwtExpirationMs", 3600000L);
        ReflectionTestUtils.setField(provider, "cookieName", "jwt");
    }

    @Test
    void generateToken_isNotBlank() {
        String token = provider.generateToken(UUID.randomUUID());
        assertThat(token).isNotBlank();
    }

    @Test
    void isTokenValid_validToken_returnsTrue() {
        String token = provider.generateToken(UUID.randomUUID());
        assertThat(provider.isTokenValid(token)).isTrue();
    }

    @Test
    void isTokenValid_garbage_returnsFalse() {
        assertThat(provider.isTokenValid("not.a.token")).isFalse();
    }

    @Test
    void getUserIdFromToken_roundtrip() {
        UUID userId = UUID.randomUUID();
        String token = provider.generateToken(userId);
        String extracted = provider.getUserIdFromToken(token);
        assertThat(extracted).isEqualTo(userId.toString());
    }

    @Test
    void getUserIdFromToken_invalid_returnsNull() {
        assertThat(provider.getUserIdFromToken("garbage")).isNull();
    }

    @Test
    void getCookieName_returnsConfiguredName() {
        assertThat(provider.getCookieName()).isEqualTo("jwt");
    }
}
