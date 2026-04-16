package com.healthmate.medications.dto;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.List;

@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class UserMedicationsPageResponse {
    private List<UserMedicationResponse> active;
    private List<UserMedicationResponse> inactive;
    private int page;
    private int size;
    private long total;
}
