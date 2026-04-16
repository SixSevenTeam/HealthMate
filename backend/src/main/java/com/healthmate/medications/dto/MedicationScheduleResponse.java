package com.healthmate.medications.dto;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalTime;
import java.util.List;
import java.util.UUID;

@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class MedicationScheduleResponse {
    private UUID id;
    private LocalTime timeOfDay;
    private List<Integer> daysOfWeek;
}
