package com.healthmate.common.encryption;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import javax.crypto.Cipher;
import javax.crypto.SecretKey;
import javax.crypto.spec.SecretKeySpec;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.Base64;

@Service
public class EncryptionService {

    @Value("${aes.secret-key}")
    private String secretKeyString;

    private static final String ALGORITHM = "AES";

    private SecretKey getSecretKey() {
        byte[] keyBytes;
        try {
            keyBytes = Base64.getDecoder().decode(secretKeyString);
            if (keyBytes.length != 16 && keyBytes.length != 24 && keyBytes.length != 32) {
                keyBytes = deriveKey(secretKeyString);
            }
        } catch (IllegalArgumentException e) {
            keyBytes = deriveKey(secretKeyString);
        }
        return new SecretKeySpec(keyBytes, ALGORITHM);
    }

    private byte[] deriveKey(String source) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            return digest.digest(source.getBytes(StandardCharsets.UTF_8));
        } catch (Exception e) {
            throw new RuntimeException("Error deriving AES key", e);
        }
    }

    public String encrypt(String data) {
        if (data == null || data.isEmpty()) {
            return data;
        }
        try {
            Cipher cipher = Cipher.getInstance(ALGORITHM);
            cipher.init(Cipher.ENCRYPT_MODE, getSecretKey());
            byte[] encryptedData = cipher.doFinal(data.getBytes());
            return Base64.getEncoder().encodeToString(encryptedData);
        } catch (Exception e) {
            throw new RuntimeException("Error encrypting data", e);
        }
    }

    public String decrypt(String encryptedData) {
        if (encryptedData == null || encryptedData.isEmpty()) {
            return encryptedData;
        }
        if (encryptedData.trim().startsWith("[") || encryptedData.trim().startsWith("{")) {
            return encryptedData;
        }
        try {
            Cipher cipher = Cipher.getInstance(ALGORITHM);
            cipher.init(Cipher.DECRYPT_MODE, getSecretKey());
            byte[] decodedData = Base64.getDecoder().decode(encryptedData);
            byte[] decryptedData = cipher.doFinal(decodedData);
            return new String(decryptedData);
        } catch (Exception e) {
            return encryptedData;
        }
    }
}
