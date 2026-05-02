package com.healthmate.medications.dto;

import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Pattern;
import java.time.LocalDate;
import java.util.UUID;
import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@NoArgsConstructor
@AllArgsConstructor
public class MarkIntakeRequest {

    @NotNull
    private UUID scheduleId;

    @NotNull
    private LocalDate date;

    @NotNull
    @Pattern(regexp = "^(taken|missed|skipped)$", message = "status must be one of: taken, missed, skipped")
    private String status;
}
