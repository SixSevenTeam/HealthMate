package com.healthmate.common.encryption;


import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.test.util.ReflectionTestUtils;


class EncryptionServiceTest {

    EncryptionService encryptionService;

    @BeforeEach
    void setUp() {
        encryptionService = new EncryptionService();
        ReflectionTestUtils.setField(
                encryptionService,
                "secretKeyString",
                "healthmate_aes_secret_key_change_in_prod_32chars");
    }

    @Test
    void encrypt_notNullOrBlank() {
        String result = encryptionService.encrypt("hello");
        assertThat(result).isNotBlank();
        assertThat(result).isNotEqualTo("hello");
    }

    @Test
    void encrypt_thenDecrypt_roundtrip() {
        String original = "[{\"name\":\"Гипертония\"}]";
        String encrypted = encryptionService.encrypt(original);
        String decrypted = encryptionService.decrypt(encrypted);
        assertThat(decrypted).isEqualTo(original);
    }

    @Test
    void encrypt_null_returnsNull() {
        assertThat(encryptionService.encrypt(null)).isNull();
    }

    @Test
    void encrypt_empty_returnsEmpty() {
        assertThat(encryptionService.encrypt("")).isEmpty();
    }

    @Test
    void decrypt_null_returnsNull() {
        assertThat(encryptionService.decrypt(null)).isNull();
    }

    @Test
    void decrypt_empty_returnsEmpty() {
        assertThat(encryptionService.decrypt("")).isEmpty();
    }

    @Test
    void decrypt_plaintextJson_returnedAsIs() {
        String json = "[{\"allergen\":\"пенициллин\"}]";
        String result = encryptionService.decrypt(json);
        assertThat(result).isEqualTo(json);
    }

    @Test
    void encrypt_differentValues_produceDifferentCiphertext() {
        String a = encryptionService.encrypt("valueA");
        String b = encryptionService.encrypt("valueB");
        assertThat(a).isNotEqualTo(b);
    }
}
