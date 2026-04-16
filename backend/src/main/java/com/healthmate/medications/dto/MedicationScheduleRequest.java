package com.healthmate.medications.dto;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotEmpty;
import jakarta.validation.constraints.NotNull;
import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalTime;
import java.util.List;

@Data
@NoArgsConstructor
@AllArgsConstructor
public class MedicationScheduleRequest {

    @NotNull
    private LocalTime timeOfDay;

    @NotEmpty
    private List<@Min(1) @Max(7) Integer> daysOfWeek;
}
