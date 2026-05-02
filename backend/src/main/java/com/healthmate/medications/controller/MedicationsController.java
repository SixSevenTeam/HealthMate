package com.healthmate.medications.controller;

import com.healthmate.aigateway.dto.MedicationSafetyRequest;
import com.healthmate.aigateway.dto.MedicationSafetyResponse;
import com.healthmate.aigateway.service.AIGatewayService;
import com.healthmate.auth.service.AuthService;
import com.healthmate.medications.dto.CreateMedicationRequest;
import com.healthmate.medications.dto.IntakeLogResponse;
import com.healthmate.medications.dto.IntakeLogStatusRequest;
import com.healthmate.medications.dto.IntakeLogsResponse;
import com.healthmate.medications.dto.MarkIntakeRequest;
import com.healthmate.medications.dto.MedicationValidationRequest;
import com.healthmate.medications.dto.MedicationScheduleRequest;
import com.healthmate.medications.dto.MedicationScheduleResponse;
import com.healthmate.medications.dto.MedicationStatusRequest;
import com.healthmate.medications.dto.UserMedicationResponse;
import com.healthmate.medications.dto.UserMedicationsPageResponse;
import com.healthmate.medications.entity.Schedule;
import com.healthmate.medications.entity.UserMedication;
import com.healthmate.medications.service.MedicationsService;
import com.healthmate.profile.service.ProfileService;
import com.healthmate.profile.service.UserContextDTO;
import com.healthmate.exception.ErrorResponse;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.media.ArraySchema;
import io.swagger.v3.oas.annotations.media.Content;
import io.swagger.v3.oas.annotations.media.ExampleObject;
import io.swagger.v3.oas.annotations.media.Schema;
import io.swagger.v3.oas.annotations.responses.ApiResponse;
import io.swagger.v3.oas.annotations.responses.ApiResponses;
import io.swagger.v3.oas.annotations.security.SecurityRequirement;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import org.springframework.data.domain.PageRequest;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.time.Instant;
import java.time.LocalDate;
import java.time.ZoneId;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashMap;
import java.util.List;
import java.util.UUID;
import java.util.stream.Collectors;

@RestController
@RequestMapping("/api/medications")
@Tag(name = "Medications", description = "Medication tracker, schedules, intake logs, and safety validation")
@SecurityRequirement(name = "cookieAuth")
public class MedicationsController {

    private final MedicationsService medicationsService;
    private final AIGatewayService aiGatewayService;
    private final ProfileService profileService;
    private final AuthService authService;

    public MedicationsController(
        MedicationsService medicationsService,
        AIGatewayService aiGatewayService,
        ProfileService profileService,
        AuthService authService
    ) {
        this.medicationsService = medicationsService;
        this.aiGatewayService = aiGatewayService;
        this.profileService = profileService;
        this.authService = authService;
    }

    @GetMapping
    @Operation(summary = "List user medications", description = "Returns active and inactive medications with pagination metadata")
    @ApiResponses(value = {
        @ApiResponse(responseCode = "200", description = "Medications page", content = @Content(schema = @Schema(implementation = UserMedicationsPageResponse.class))),
        @ApiResponse(responseCode = "401", description = "Unauthorized", content = @Content(schema = @Schema(implementation = ErrorResponse.class)))
    })
    public ResponseEntity<UserMedicationsPageResponse> getMedications(
        @Parameter(description = "Page number (0-based)", example = "0")
        @RequestParam(defaultValue = "0") int page,
        @Parameter(description = "Page size", example = "20")
        @RequestParam(defaultValue = "20") int size
    ) {
        UUID userId = getUserId();
        var paged = medicationsService.getUserMedications(userId, PageRequest.of(page, size));

        List<UserMedicationResponse> mapped = paged.getContent().stream()
            .map(item -> toMedicationResponse(item, null))
            .collect(Collectors.toList());

        List<UserMedicationResponse> active = mapped.stream()
            .filter(item -> Boolean.TRUE.equals(item.getIsActive()))
            .collect(Collectors.toList());

        List<UserMedicationResponse> inactive = mapped.stream()
            .filter(item -> !Boolean.TRUE.equals(item.getIsActive()))
            .collect(Collectors.toList());

        UserMedicationsPageResponse response = UserMedicationsPageResponse.builder()
            .active(active)
            .inactive(inactive)
            .page(page)
            .size(size)
            .total(paged.getTotalElements())
            .build();

        return ResponseEntity.ok(response);
    }

    @PostMapping
    @Operation(summary = "Create medication", description = "Creates medication with schedules and returns enriched medication info with safety warnings")
    @ApiResponses(value = {
        @ApiResponse(responseCode = "201", description = "Medication created", content = @Content(schema = @Schema(implementation = UserMedicationResponse.class))),
        @ApiResponse(responseCode = "400", description = "Validation error", content = @Content(schema = @Schema(implementation = ErrorResponse.class))),
        @ApiResponse(responseCode = "401", description = "Unauthorized", content = @Content(schema = @Schema(implementation = ErrorResponse.class))),
        @ApiResponse(responseCode = "503", description = "AI service unavailable", content = @Content(schema = @Schema(implementation = ErrorResponse.class)))
    })
    public ResponseEntity<UserMedicationResponse> createMedication(@Valid @RequestBody CreateMedicationRequest request) {
        UUID userId = getUserId();
        MedicationSafetyResponse safety = runMedicationSafetyValidation(userId, request);

        UserMedication medication = UserMedication.builder()
            .drugId(request.getDrugId())
            .customName(request.getCustomName())
            .doseAmount(request.getDoseAmount())
            .doseUnit(request.getDoseUnit())
            .instructions(request.getInstructions())
            .startDate(request.getStartDate())
            .endDate(request.getEndDate())
            .isActive(true)
            .build();

        List<Schedule> schedules = request.getSchedules().stream()
            .map(this::toScheduleEntity)
            .collect(Collectors.toList());

        UserMedication saved = medicationsService.createMedicationWithSchedules(userId, medication, schedules);
        return ResponseEntity.status(HttpStatus.CREATED).body(toMedicationResponse(saved, safety));
    }

    @PostMapping("/validate")
    @Operation(summary = "Validate medication safety", description = "Runs non-blocking AI safety validation for candidate medication")
    @ApiResponses(value = {
        @ApiResponse(responseCode = "200", description = "Validation result", content = @Content(examples = @ExampleObject(value = "{\"status\":\"warning\",\"warnings\":[\"Potential interaction\"],\"blockers\":[],\"metadata\":{}}"))),
        @ApiResponse(responseCode = "400", description = "Validation error", content = @Content(schema = @Schema(implementation = ErrorResponse.class))),
        @ApiResponse(responseCode = "401", description = "Unauthorized", content = @Content(schema = @Schema(implementation = ErrorResponse.class))),
        @ApiResponse(responseCode = "503", description = "AI service unavailable", content = @Content(schema = @Schema(implementation = ErrorResponse.class)))
    })
    public ResponseEntity<?> validateMedication(@Valid @RequestBody MedicationValidationRequest request) {
        UUID userId = getUserId();
        MedicationSafetyResponse safety = runMedicationSafetyValidation(userId, request);

        HashMap<String, Object> response = new HashMap<>();
        response.put("status", safety.normalizedStatus());
        response.put("warnings", safety.safeWarnings());
        response.put("blockers", safety.safeBlockers());
        response.put("metadata", safety.getMetadata());
        return ResponseEntity.ok(response);
    }

    @DeleteMapping("/{id}")
    @Operation(summary = "Deactivate medication", description = "Soft-deactivates medication for current user")
    @ApiResponses(value = {
        @ApiResponse(responseCode = "200", description = "Medication deactivated", content = @Content(examples = @ExampleObject(value = "{\"id\":\"00000000-0000-0000-0000-000000000000\",\"isActive\":false}"))),
        @ApiResponse(responseCode = "401", description = "Unauthorized", content = @Content(schema = @Schema(implementation = ErrorResponse.class))),
        @ApiResponse(responseCode = "404", description = "Medication not found", content = @Content(schema = @Schema(implementation = ErrorResponse.class)))
    })
    public ResponseEntity<?> deactivateMedication(@PathVariable UUID id) {
        UUID userId = getUserId();
        medicationsService.deactivateUserMedication(id, userId);
        return ResponseEntity.ok(java.util.Map.of("id", id, "isActive", false));
    }

    @PutMapping("/{id}/active")
    @Operation(summary = "Set medication active status", description = "Activates or deactivates medication")
    @ApiResponses(value = {
        @ApiResponse(responseCode = "200", description = "Status changed", content = @Content(examples = @ExampleObject(value = "{\"id\":\"00000000-0000-0000-0000-000000000000\",\"isActive\":true}"))),
        @ApiResponse(responseCode = "400", description = "Validation error", content = @Content(schema = @Schema(implementation = ErrorResponse.class))),
        @ApiResponse(responseCode = "401", description = "Unauthorized", content = @Content(schema = @Schema(implementation = ErrorResponse.class))),
        @ApiResponse(responseCode = "404", description = "Medication not found", content = @Content(schema = @Schema(implementation = ErrorResponse.class)))
    })
    public ResponseEntity<?> setMedicationActive(@PathVariable UUID id, @Valid @RequestBody MedicationStatusRequest request) {
        UUID userId = getUserId();
        UserMedication updated = medicationsService.setMedicationActive(id, userId, request.getIsActive());
        return ResponseEntity.ok(java.util.Map.of("id", updated.getId(), "isActive", updated.getIsActive()));
    }

    @GetMapping("/{id}/schedules")
    @Operation(summary = "List schedules", description = "Returns schedules for medication")
    @ApiResponses(value = {
        @ApiResponse(responseCode = "200", description = "Schedules list", content = @Content(array = @ArraySchema(schema = @Schema(implementation = MedicationScheduleResponse.class)))),
        @ApiResponse(responseCode = "401", description = "Unauthorized", content = @Content(schema = @Schema(implementation = ErrorResponse.class))),
        @ApiResponse(responseCode = "404", description = "Medication not found", content = @Content(schema = @Schema(implementation = ErrorResponse.class)))
    })
    public ResponseEntity<List<MedicationScheduleResponse>> getSchedules(@PathVariable UUID id) {
        UUID userId = getUserId();
        List<MedicationScheduleResponse> response = medicationsService.getSchedules(id, userId).stream()
            .map(this::toScheduleResponse)
            .collect(Collectors.toList());
        return ResponseEntity.ok(response);
    }

    @PostMapping("/{id}/schedules")
    @Operation(summary = "Add schedule", description = "Adds a schedule to medication")
    @ApiResponses(value = {
        @ApiResponse(responseCode = "201", description = "Schedule created", content = @Content(schema = @Schema(implementation = MedicationScheduleResponse.class))),
        @ApiResponse(responseCode = "400", description = "Validation error", content = @Content(schema = @Schema(implementation = ErrorResponse.class))),
        @ApiResponse(responseCode = "401", description = "Unauthorized", content = @Content(schema = @Schema(implementation = ErrorResponse.class))),
        @ApiResponse(responseCode = "404", description = "Medication not found", content = @Content(schema = @Schema(implementation = ErrorResponse.class)))
    })
    public ResponseEntity<MedicationScheduleResponse> addSchedule(
        @PathVariable UUID id,
        @Valid @RequestBody MedicationScheduleRequest request
    ) {
        UUID userId = getUserId();
        Schedule saved = medicationsService.addSchedule(id, userId, toScheduleEntity(request));
        return ResponseEntity.status(HttpStatus.CREATED).body(toScheduleResponse(saved));
    }

    @DeleteMapping("/schedules/{scheduleId}")
    @Operation(summary = "Delete schedule", description = "Deletes schedule by id")
    @ApiResponses(value = {
        @ApiResponse(responseCode = "200", description = "Schedule deleted", content = @Content(examples = @ExampleObject(value = "{\"id\":\"00000000-0000-0000-0000-000000000000\",\"deleted\":true}"))),
        @ApiResponse(responseCode = "401", description = "Unauthorized", content = @Content(schema = @Schema(implementation = ErrorResponse.class))),
        @ApiResponse(responseCode = "404", description = "Schedule not found", content = @Content(schema = @Schema(implementation = ErrorResponse.class)))
    })
    public ResponseEntity<?> deleteSchedule(@PathVariable UUID scheduleId) {
        UUID userId = getUserId();
        medicationsService.deleteSchedule(scheduleId, userId);
        return ResponseEntity.ok(java.util.Map.of("id", scheduleId, "deleted", true));
    }

    @GetMapping("/{id}/intake-logs")
    @Operation(summary = "Get intake logs", description = "Returns intake logs for medication in date range. If from/to not provided, defaults to today ±7 days")
    @ApiResponses(value = {
        @ApiResponse(responseCode = "200", description = "Intake logs returned", content = @Content(schema = @Schema(implementation = IntakeLogsResponse.class))),
        @ApiResponse(responseCode = "400", description = "Validation error", content = @Content(schema = @Schema(implementation = ErrorResponse.class))),
        @ApiResponse(responseCode = "401", description = "Unauthorized", content = @Content(schema = @Schema(implementation = ErrorResponse.class))),
        @ApiResponse(responseCode = "404", description = "Medication not found", content = @Content(schema = @Schema(implementation = ErrorResponse.class)))
    })
    public ResponseEntity<IntakeLogsResponse> getIntakeLogs(
        @PathVariable UUID id,
        @Parameter(description = "From date (inclusive), format yyyy-MM-dd. Defaults to today", example = "2026-04-01")
        @RequestParam(required = false) LocalDate from,
        @Parameter(description = "To date (inclusive), format yyyy-MM-dd. Defaults to 7 days from today", example = "2026-04-07")
        @RequestParam(required = false) LocalDate to
    ) {
        UUID userId = getUserId();
        ZoneId zone = ZoneId.systemDefault();
        
        // Set defaults if not provided
        LocalDate fromDate = from != null ? from : LocalDate.now(zone);
        LocalDate toDate = to != null ? to : LocalDate.now(zone).plusDays(7);
        
        Instant fromInstant = fromDate.atStartOfDay(zone).toInstant();
        Instant toInstant = toDate.plusDays(1).atStartOfDay(zone).toInstant();

        List<IntakeLogResponse> logs = medicationsService.getIntakeLogs(id, userId, fromInstant, toInstant).stream()
            .map(log -> IntakeLogResponse.builder()
                .id(log.getId())
                .scheduledAt(log.getScheduledAt())
                .takenAt(log.getTakenAt())
                .status(log.getStatus())
                .confirmedVia(log.getConfirmedVia())
                .build())
            .collect(Collectors.toList());

        return ResponseEntity.ok(IntakeLogsResponse.builder().logs(logs).build());
    }

    @PostMapping("/intake-logs/{logId}/take")
    @Operation(summary = "Confirm intake", description = "Marks intake log as taken")
    @ApiResponses(value = {
        @ApiResponse(responseCode = "200", description = "Intake confirmed", content = @Content(examples = @ExampleObject(value = "{\"id\":\"00000000-0000-0000-0000-000000000000\",\"status\":\"taken\"}"))),
        @ApiResponse(responseCode = "401", description = "Unauthorized", content = @Content(schema = @Schema(implementation = ErrorResponse.class))),
        @ApiResponse(responseCode = "404", description = "Intake log not found", content = @Content(schema = @Schema(implementation = ErrorResponse.class)))
    })
    public ResponseEntity<?> takeMedication(@PathVariable UUID logId) {
        UUID userId = getUserId();
        medicationsService.confirmIntake(logId, userId);
        return ResponseEntity.ok(java.util.Map.of("id", logId, "status", "taken"));
    }

    @PatchMapping("/intake-logs/{logId}/status")
    @Operation(summary = "Set intake status", description = "Updates intake status to taken/missed/skipped")
    @ApiResponses(value = {
        @ApiResponse(responseCode = "200", description = "Status updated", content = @Content(examples = @ExampleObject(value = "{\"id\":\"00000000-0000-0000-0000-000000000000\",\"status\":\"missed\"}"))),
        @ApiResponse(responseCode = "400", description = "Validation error", content = @Content(schema = @Schema(implementation = ErrorResponse.class))),
        @ApiResponse(responseCode = "401", description = "Unauthorized", content = @Content(schema = @Schema(implementation = ErrorResponse.class))),
        @ApiResponse(responseCode = "404", description = "Intake log not found", content = @Content(schema = @Schema(implementation = ErrorResponse.class)))
    })
    public ResponseEntity<?> updateIntakeStatus(
        @PathVariable UUID logId,
        @Valid @RequestBody IntakeLogStatusRequest request
    ) {
        UUID userId = getUserId();
        var updated = medicationsService.setIntakeStatus(logId, userId, request.getStatus());
        return ResponseEntity.ok(java.util.Map.of("id", logId, "status", updated.getStatus()));
    }

    @PostMapping("/{medicationId}/intake-logs/mark")
    @Operation(summary = "Mark intake by date", description = "Marks or backfills an intake log for the selected schedule and date")
    @ApiResponses(value = {
        @ApiResponse(responseCode = "200", description = "Intake marked", content = @Content(examples = @ExampleObject(value = "{\"id\":\"00000000-0000-0000-0000-000000000000\",\"status\":\"taken\"}"))),
        @ApiResponse(responseCode = "400", description = "Validation error", content = @Content(schema = @Schema(implementation = ErrorResponse.class))),
        @ApiResponse(responseCode = "401", description = "Unauthorized", content = @Content(schema = @Schema(implementation = ErrorResponse.class))),
        @ApiResponse(responseCode = "404", description = "Medication or schedule not found", content = @Content(schema = @Schema(implementation = ErrorResponse.class)))
    })
    public ResponseEntity<?> markIntake(
        @PathVariable UUID medicationId,
        @Valid @RequestBody MarkIntakeRequest request
    ) {
        UUID userId = getUserId();
        var updated = medicationsService.markIntake(
            medicationId,
            request.getScheduleId(),
            request.getDate(),
            userId,
            request.getStatus()
        );
        HashMap<String, Object> resp = new HashMap<>();
        resp.put("id", updated.getId());
        resp.put("status", updated.getStatus());
        resp.put("scheduledAt", updated.getScheduledAt());
        resp.put("takenAt", updated.getTakenAt());
        return ResponseEntity.ok(resp);
    }

    private UserMedicationResponse toMedicationResponse(UserMedication medication, MedicationSafetyResponse safetyResponse) {
        List<MedicationScheduleResponse> schedules = medicationsService.getSchedules(medication.getId(), medication.getUserId()).stream()
            .map(this::toScheduleResponse)
            .collect(Collectors.toList());

        String doseWarning = medicationsService.calculateDoseWarning(medication);
        List<String> safetyWarnings = new ArrayList<>();
        if (safetyResponse != null) {
            safetyWarnings.addAll(safetyResponse.safeWarnings());
            safetyWarnings.addAll(safetyResponse.safeBlockers());
        }
        if (doseWarning != null && !doseWarning.isBlank()) {
            safetyWarnings.add(doseWarning);
        }

        return UserMedicationResponse.builder()
            .id(medication.getId())
            .tradeName(medicationsService.resolveTradeName(medication))
            .customName(medication.getCustomName())
            .doseAmount(medication.getDoseAmount())
            .doseUnit(medication.getDoseUnit())
            .instructions(medication.getInstructions())
            .doseWarning(doseWarning)
            .safetyStatus(safetyResponse == null ? "unknown" : safetyResponse.normalizedStatus())
            .safetyWarnings(safetyWarnings)
            .isActive(medication.getIsActive())
            .startDate(medication.getStartDate())
            .endDate(medication.getEndDate())
            .schedules(schedules)
            .build();
    }

    private MedicationSafetyResponse runMedicationSafetyValidation(UUID userId, CreateMedicationRequest request) {
        return runMedicationSafetyValidation(
            userId,
            request.getDrugId(),
            request.getCustomName(),
            request.getDoseAmount(),
            request.getDoseUnit(),
            request.getInstructions(),
            request.getStartDate(),
            request.getEndDate()
        );
    }

    private MedicationSafetyResponse runMedicationSafetyValidation(UUID userId, MedicationValidationRequest request) {
        return runMedicationSafetyValidation(
            userId,
            request.getDrugId(),
            request.getCustomName(),
            request.getDoseAmount(),
            request.getDoseUnit(),
            request.getInstructions(),
            request.getStartDate(),
            request.getEndDate()
        );
    }

    private MedicationSafetyResponse runMedicationSafetyValidation(
        UUID userId,
        UUID drugId,
        String customName,
        java.math.BigDecimal doseAmount,
        String doseUnit,
        String instructions,
        LocalDate startDate,
        LocalDate endDate
    ) {
        UserContextDTO userContext = profileService.getUserContext(userId);
        userContext.setBirthDate(authService.getUserEntity(userId).getBirthDate());
        userContext.setActiveMedications(medicationsService.getActiveMedicationsForContext(userId));

        MedicationSafetyRequest request = MedicationSafetyRequest.builder()
            .userId(userId)
            .userContext(userContext)
            .candidateMedication(MedicationSafetyRequest.CandidateMedication.builder()
                .drugId(drugId)
                .customName(customName)
                .doseAmount(doseAmount)
                .doseUnit(doseUnit)
                .instructions(instructions)
                .startDate(startDate)
                .endDate(endDate)
                .build())
            .build();

        return aiGatewayService.validateMedication(request);
    }

    private Schedule toScheduleEntity(MedicationScheduleRequest request) {
        return Schedule.builder()
            .timeOfDay(request.getTimeOfDay())
            .daysOfWeek(request.getDaysOfWeek().toArray(new Integer[0]))
            .build();
    }

    private MedicationScheduleResponse toScheduleResponse(Schedule schedule) {
        return MedicationScheduleResponse.builder()
            .id(schedule.getId())
            .timeOfDay(schedule.getTimeOfDay())
            .daysOfWeek(Arrays.asList(schedule.getDaysOfWeek()))
            .build();
    }

    private UUID getUserId() {
        Object principal = SecurityContextHolder.getContext().getAuthentication().getPrincipal();
        return UUID.fromString((String) principal);
    }
}
