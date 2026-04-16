package com.healthmate.profile.controller;

import com.healthmate.profile.dto.MedicalProfileRequest;
import com.healthmate.profile.dto.MedicalProfileResponse;
import com.healthmate.profile.service.ProfileService;
import com.healthmate.exception.ErrorResponse;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.media.Content;
import io.swagger.v3.oas.annotations.media.ExampleObject;
import io.swagger.v3.oas.annotations.media.Schema;
import io.swagger.v3.oas.annotations.responses.ApiResponse;
import io.swagger.v3.oas.annotations.responses.ApiResponses;
import io.swagger.v3.oas.annotations.security.SecurityRequirement;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.web.bind.annotation.*;

import java.util.UUID;

@RestController
@RequestMapping("/api/profile")
@Tag(name = "Profile", description = "Medical profile CRUD")
@SecurityRequirement(name = "cookieAuth")
public class ProfileController {

    private final ProfileService profileService;

    public ProfileController(ProfileService profileService) {
        this.profileService = profileService;
    }

    @GetMapping
    @Operation(summary = "Get medical profile", description = "Returns current user's medical profile")
    @ApiResponses(value = {
        @ApiResponse(responseCode = "200", description = "Profile returned", content = @Content(schema = @Schema(implementation = MedicalProfileResponse.class))),
        @ApiResponse(responseCode = "401", description = "Unauthorized", content = @Content(schema = @Schema(implementation = ErrorResponse.class))),
        @ApiResponse(responseCode = "404", description = "Profile not found", content = @Content(schema = @Schema(implementation = ErrorResponse.class)))
    })
    public ResponseEntity<MedicalProfileResponse> getProfile() {
        UUID userId = getUserId();
        MedicalProfileResponse response = profileService.getProfile(userId);
        return ResponseEntity.ok(response);
    }

    @PutMapping
    @Operation(summary = "Update medical profile", description = "Creates or updates current user's medical profile")
    @ApiResponses(value = {
        @ApiResponse(responseCode = "200", description = "Profile updated", content = @Content(examples = @ExampleObject(value = "{\"updatedAt\":\"2026-04-02T12:00:00Z\"}"))),
        @ApiResponse(responseCode = "400", description = "Validation error", content = @Content(schema = @Schema(implementation = ErrorResponse.class))),
        @ApiResponse(responseCode = "401", description = "Unauthorized", content = @Content(schema = @Schema(implementation = ErrorResponse.class)))
    })
    public ResponseEntity<?> updateProfile(@Valid @RequestBody MedicalProfileRequest request) {
        UUID userId = getUserId();
        java.time.Instant updatedAt = profileService.updateProfile(userId, request);
        return ResponseEntity.ok(java.util.Map.of("updatedAt", updatedAt));
    }

    private UUID getUserId() {
        Object principal = SecurityContextHolder.getContext().getAuthentication().getPrincipal();
        return UUID.fromString((String) principal);
    }
}
