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

    @GetMapping("/mappings")
    @Operation(summary = "Get all drug mappings", description = "Returns list of drug id and source paths for indexing")
    public ResponseEntity<java.util.List<com.healthmate.medications.dto.DrugMappingResponse>> getAllMappings() {
        var list = medicationsService.getAllDrugMappings();
        return ResponseEntity.ok(list);
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

    @GetMapping(value = "/{drugId}")
    @Operation(summary = "Get drug metadata", description = "Returns JSON metadata for a drug by id")
    public ResponseEntity<DrugSearchResponse.DrugSearchItem> getDrugMetadata(@PathVariable UUID drugId) {
        var d = medicationsService.getDrugById(drugId);

        DrugSearchResponse.DrugSearchItem item = DrugSearchResponse.DrugSearchItem.builder()
            .id(d.getId())
            .tradeName(d.getTradeName())
            .internationalName(d.getInternationalName())
            .atxCode(d.getAtxCode())
            .doseUnit(d.getDoseUnit())
            .minDose(d.getMinDose())
            .maxDose(d.getMaxDose())
            .isInRag(d.getIsInRag())
            .hasMedia(d.getPackImagePath() != null && !d.getPackImagePath().isBlank())
            .build();

        return ResponseEntity.ok(item);
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
