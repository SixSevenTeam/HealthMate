package com.healthmate.medications.job;

import com.healthmate.medications.service.MedicationsService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

@Slf4j
@Component
@RequiredArgsConstructor
public class OverdueIntakeStatusJob {

    private final MedicationsService medicationsService;

    @Scheduled(cron = "0 5 0 * * *")
    public void markOverduePendingLogsAsMissed() {
        int updated = medicationsService.markOverduePendingIntakeLogs();
        if (updated > 0) {
            log.info("Overdue intake job completed, updated {} log(s)", updated);
        }
    }
}