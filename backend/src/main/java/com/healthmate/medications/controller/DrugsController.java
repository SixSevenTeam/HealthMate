package com.healthmate.medications.controller;

import com.healthmate.medications.dto.DrugSearchResponse;
import com.healthmate.medications.service.MedicationsService;
import com.healthmate.exception.ErrorResponse;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.media.Content;
import io.swagger.v3.oas.annotations.media.Schema;
import io.swagger.v3.oas.annotations.responses.ApiResponse;
import io.swagger.v3.oas.annotations.responses.ApiResponses;
import io.swagger.v3.oas.annotations.security.SecurityRequirement;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.core.io.Resource;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.UUID;
import java.util.stream.Collectors;

@RestController
@RequestMapping("/api/drugs")
@Tag(name = "Drugs", description = "Drug catalog search")
@SecurityRequirement(name = "cookieAuth")
public class DrugsController {

    private final MedicationsService medicationsService;

    public DrugsController(MedicationsService medicationsService) {
        this.medicationsService = medicationsService;
    }

    @GetMapping("/search")
    @Operation(summary = "Search drugs", description = "Performs fuzzy search in drug catalog")
    @ApiResponses(value = {
        @ApiResponse(responseCode = "200", description = "Search results", content = @Content(schema = @Schema(implementation = DrugSearchResponse.class))),
        @ApiResponse(responseCode = "401", description = "Unauthorized", content = @Content(schema = @Schema(implementation = ErrorResponse.class)))
    })
    public ResponseEntity<DrugSearchResponse> searchDrugs(@RequestParam String q) {
        var items = medicationsService.searchDrugs(q).stream()
            .map(drug -> DrugSearchResponse.DrugSearchItem.builder()
                .id(drug.getId())
                .tradeName(drug.getTradeName())
                .internationalName(drug.getInternationalName())
                .atxCode(drug.getAtxCode())
                .doseUnit(drug.getDoseUnit())
                .minDose(drug.getMinDose())
                .maxDose(drug.getMaxDose())
                .isInRag(drug.getIsInRag())
                .hasMedia(drug.getPackImagePath() != null && !drug.getPackImagePath().isBlank())
                .build())
            .collect(Collectors.toList());

        return ResponseEntity.ok(DrugSearchResponse.builder().results(items).build());
    }

    @GetMapping(value = "/{drugId}/details", produces = MediaType.TEXT_HTML_VALUE)
    @Operation(summary = "Get drug details HTML", description = "Returns full HTML page for selected drug")
    @ApiResponses(value = {
        @ApiResponse(responseCode = "200", description = "Drug details HTML"),
        @ApiResponse(responseCode = "404", description = "Drug or details page not found", content = @Content(schema = @Schema(implementation = ErrorResponse.class))),
        @ApiResponse(responseCode = "401", description = "Unauthorized", content = @Content(schema = @Schema(implementation = ErrorResponse.class)))
    })
    public ResponseEntity<String> getDrugDetailsHtml(@PathVariable UUID drugId) {
        String html = medicationsService.getDrugDetailsHtml(drugId);
        return ResponseEntity.ok()
            .contentType(MediaType.TEXT_HTML)
            .body(html);
    }

    @GetMapping("/{drugId}/pack-image")
    @Operation(summary = "Get drug pack image", description = "Returns local image for selected drug pack")
    @ApiResponses(value = {
        @ApiResponse(responseCode = "200", description = "Drug image binary"),
        @ApiResponse(responseCode = "404", description = "Drug image not found", content = @Content(schema = @Schema(implementation = ErrorResponse.class))),
        @ApiResponse(responseCode = "401", description = "Unauthorized", content = @Content(schema = @Schema(implementation = ErrorResponse.class)))
    })
    public ResponseEntity<Resource> getDrugPackImage(@PathVariable UUID drugId) {
        MedicationsService.DrugImagePayload payload = medicationsService.getDrugPackImagePayload(drugId);

        MediaType mediaType;
        try {
            mediaType = MediaType.parseMediaType(payload.contentType());
        } catch (Exception ex) {
            mediaType = MediaType.APPLICATION_OCTET_STREAM;
        }

        return ResponseEntity.ok()
            .contentType(mediaType)
            .body(payload.image());
    }
}
