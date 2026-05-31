package com.healthmate.dashboard.controller;

import com.healthmate.dashboard.service.DashboardService;
import com.healthmate.dashboard.service.DashboardSummaryResponse;
import com.healthmate.exception.ErrorResponse;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.media.Content;
import io.swagger.v3.oas.annotations.media.Schema;
import io.swagger.v3.oas.annotations.responses.ApiResponse;
import io.swagger.v3.oas.annotations.responses.ApiResponses;
import io.swagger.v3.oas.annotations.security.SecurityRequirement;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.time.LocalDate;
import java.util.UUID;

@RestController
@RequestMapping("/api/dashboard")
@Tag(name = "Dashboard", description = "Adherence summary and insights")
@SecurityRequirement(name = "cookieAuth")
public class DashboardController {

    private final DashboardService dashboardService;

    public DashboardController(DashboardService dashboardService) {
        this.dashboardService = dashboardService;
    }

    @GetMapping("/summary")
    @Operation(summary = "Get adherence summary", description = "Returns medication adherence metrics for selected date range")
    @ApiResponses(value = {
        @ApiResponse(responseCode = "200", description = "Summary returned", content = @Content(schema = @Schema(implementation = DashboardSummaryResponse.class))),
        @ApiResponse(responseCode = "400", description = "Invalid date range", content = @Content(schema = @Schema(implementation = ErrorResponse.class))),
        @ApiResponse(responseCode = "401", description = "Unauthorized", content = @Content(schema = @Schema(implementation = ErrorResponse.class)))
    })
    public ResponseEntity<DashboardSummaryResponse> getSummary(
        @Parameter(description = "Start date (inclusive), format: yyyy-MM-dd. Defaults to 7 days ago", example = "2026-04-01")
        @RequestParam(required = false) LocalDate from,
        @Parameter(description = "End date (inclusive), format: yyyy-MM-dd. Defaults to today", example = "2026-04-07")
        @RequestParam(required = false) LocalDate to,
        @Parameter(description = "Medication scope: active, inactive, or all", example = "active")
        @RequestParam(defaultValue = "active") String scope) {

        LocalDate toDate = to != null ? to : LocalDate.now();
        LocalDate fromDate = from != null ? from : toDate.minusDays(6);

        if (fromDate.isAfter(toDate)) {
            throw new IllegalArgumentException("'from' date must be less than or equal to 'to' date");
        }

        UUID userId = getUserId();
        DashboardSummaryResponse summary = dashboardService.getSummary(userId, fromDate, toDate, scope);

        return ResponseEntity.ok(summary);
    }

    private UUID getUserId() {
        Object principal = SecurityContextHolder.getContext().getAuthentication().getPrincipal();
        return UUID.fromString((String) principal);
    }
}
