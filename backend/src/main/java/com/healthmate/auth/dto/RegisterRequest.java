package com.healthmate.auth.dto;

import com.healthmate.profile.dto.AllergyDTO;
import com.healthmate.profile.dto.DiagnosisDTO;
import jakarta.validation.Valid;
import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;
import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.List;
import java.util.UUID;

@Data
@NoArgsConstructor
@AllArgsConstructor
public class RegisterRequest {
    @NotBlank(message = "Email is required")
    @Email(message = "Email should be valid")
    private String email;

    @NotBlank(message = "Password is required")
    @Size(min = 8, max = 100, message = "Password must be between 8 and 100 characters")
    private String password;

    @NotBlank(message = "First name is required")
    private String firstName;

    @NotBlank(message = "Last name is required")
    private String lastName;

    @NotNull(message = "Birth date is required")
    private LocalDate birthDate;

    private Integer heightCm;

    private BigDecimal weightKg;

    private String bloodType;

    @Valid
    private List<DiagnosisDTO> diagnoses;

    @Valid
    private List<AllergyDTO> allergies;

    @Valid
    private List<InitialMedicationDTO> initialMedications;

    @Data
    @NoArgsConstructor
    @AllArgsConstructor
    public static class InitialMedicationDTO {
        private UUID drugId;
        private String customName;

        @NotNull(message = "Dose amount is required for initial medication")
        private BigDecimal doseAmount;

        @NotBlank(message = "Dose unit is required for initial medication")
        private String doseUnit;

        private String instructions;
        private LocalDate startDate;
        private LocalDate endDate;
    }
}
