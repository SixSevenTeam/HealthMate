package com.healthmate.auth.controller;

import com.healthmate.auth.dto.LoginRequest;
import com.healthmate.auth.dto.RegisterRequest;
import com.healthmate.auth.dto.UserResponse;
import com.healthmate.auth.service.AuthService;
import com.healthmate.auth.service.JwtTokenProvider;
import com.healthmate.exception.ErrorResponse;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.media.Content;
import io.swagger.v3.oas.annotations.media.ExampleObject;
import io.swagger.v3.oas.annotations.media.Schema;
import io.swagger.v3.oas.annotations.responses.ApiResponse;
import io.swagger.v3.oas.annotations.responses.ApiResponses;
import io.swagger.v3.oas.annotations.security.SecurityRequirement;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.servlet.http.HttpServletResponse;
import jakarta.validation.Valid;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseCookie;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.web.bind.annotation.*;

import java.util.Map;
import java.util.UUID;

@RestController
@RequestMapping("/api/auth")
@Tag(name = "Authentication", description = "Registration, login/logout, and current user session")
public class AuthController {

    private final AuthService authService;
    private final JwtTokenProvider jwtTokenProvider;

    @Value("${jwt.expiration-ms}")
    private long jwtExpirationMs;

    @Value("${auth.cookie-secure:false}")
    private boolean cookieSecure;

    @Value("${auth.cookie-same-site:Strict}")
    private String cookieSameSite;

    public AuthController(AuthService authService, JwtTokenProvider jwtTokenProvider) {
        this.authService = authService;
        this.jwtTokenProvider = jwtTokenProvider;
    }

    @PostMapping("/register")
    @Operation(summary = "Register a new user", description = "Creates a user account and returns the user profile")
    @ApiResponses(value = {
        @ApiResponse(responseCode = "201", description = "User registered", content = @Content(schema = @Schema(implementation = UserResponse.class))),
        @ApiResponse(responseCode = "400", description = "Validation error", content = @Content(schema = @Schema(implementation = ErrorResponse.class))),
        @ApiResponse(responseCode = "409", description = "Email already exists", content = @Content(schema = @Schema(implementation = ErrorResponse.class)))
    })
    public ResponseEntity<UserResponse> register(@Valid @RequestBody RegisterRequest request) {
        UserResponse response = authService.register(request);
        return ResponseEntity.status(HttpStatus.CREATED).body(response);
    }

    @PostMapping("/login")
    @Operation(summary = "Login", description = "Authenticates user and sets HttpOnly JWT cookie")
    @ApiResponses(value = {
        @ApiResponse(responseCode = "200", description = "Authenticated, cookie set", content = @Content(schema = @Schema(implementation = UserResponse.class))),
        @ApiResponse(responseCode = "400", description = "Validation error", content = @Content(schema = @Schema(implementation = ErrorResponse.class))),
        @ApiResponse(responseCode = "401", description = "Invalid credentials", content = @Content(schema = @Schema(implementation = ErrorResponse.class)))
    })
    public ResponseEntity<UserResponse> login(@Valid @RequestBody LoginRequest request, HttpServletResponse response) {
        AuthService.LoginResult result = authService.login(request);

        ResponseCookie cookie = ResponseCookie.from(jwtTokenProvider.getCookieName(), result.token())
            .httpOnly(true)
            .secure(cookieSecure)
            .path("/")
            .maxAge(jwtExpirationMs / 1000)
            .sameSite(cookieSameSite)
            .build();

        response.addHeader("Set-Cookie", cookie.toString());
        return ResponseEntity.ok(result.user());
    }

    @PostMapping("/logout")
    @Operation(summary = "Logout", description = "Clears JWT cookie and terminates session")
    @ApiResponses(value = {
        @ApiResponse(responseCode = "200", description = "Logged out", content = @Content(examples = @ExampleObject(value = "{\"message\":\"Logged out successfully\"}")))
    })
    public ResponseEntity<?> logout(HttpServletResponse response) {
        ResponseCookie cookie = ResponseCookie.from(jwtTokenProvider.getCookieName(), "")
            .httpOnly(true)
            .secure(cookieSecure)
            .path("/")
            .maxAge(0)
            .sameSite(cookieSameSite)
            .build();
        response.addHeader("Set-Cookie", cookie.toString());

        return ResponseEntity.ok(Map.of("message", "Logged out successfully"));
    }

    @GetMapping("/me")
    @Operation(summary = "Get current user", description = "Returns current authenticated user by JWT cookie", security = @SecurityRequirement(name = "cookieAuth"))
    @ApiResponses(value = {
        @ApiResponse(responseCode = "200", description = "Current user", content = @Content(schema = @Schema(implementation = UserResponse.class))),
        @ApiResponse(responseCode = "401", description = "Unauthorized", content = @Content(schema = @Schema(implementation = ErrorResponse.class)))
    })
    public ResponseEntity<UserResponse> getCurrentUser() {
        Object principal = SecurityContextHolder.getContext().getAuthentication().getPrincipal();
        if (principal instanceof String) {
            UUID userId = UUID.fromString((String) principal);
            UserResponse user = authService.getCurrentUser(userId);
            return ResponseEntity.ok(user);
        }
        return ResponseEntity.status(HttpStatus.UNAUTHORIZED).build();
    }
}
