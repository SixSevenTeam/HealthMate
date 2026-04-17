package com.healthmate.medications.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;
import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@NoArgsConstructor
@AllArgsConstructor
public class IntakeLogStatusRequest {

    @NotBlank
    @Pattern(regexp = "^(taken|missed|skipped)$", message = "status must be one of: taken, missed, skipped")
    private String status;
}
