package com.healthmate.config;

import io.swagger.v3.oas.annotations.OpenAPIDefinition;
import io.swagger.v3.oas.annotations.enums.SecuritySchemeIn;
import io.swagger.v3.oas.annotations.enums.SecuritySchemeType;
import io.swagger.v3.oas.annotations.info.Contact;
import io.swagger.v3.oas.annotations.info.Info;
import io.swagger.v3.oas.annotations.security.SecurityRequirement;
import io.swagger.v3.oas.annotations.security.SecurityScheme;
import io.swagger.v3.oas.annotations.servers.Server;
import org.springframework.context.annotation.Configuration;

@Configuration
@OpenAPIDefinition(
    info = @Info(
        title = "HealthMate Backend API",
        version = "v1",
        description = "API for authentication, medical profile, medications, chat assistant, and dashboard analytics.",
        contact = @Contact(name = "HealthMate Team")
    ),
    servers = {
        @Server(url = "/healthmate", description = "Default server with context path"),
        @Server(url = "", description = "Local server without context path")
    },
    security = {
        @SecurityRequirement(name = "cookieAuth")
    }
)
@SecurityScheme(
    name = "cookieAuth",
    type = SecuritySchemeType.APIKEY,
    in = SecuritySchemeIn.COOKIE,
    paramName = "jwt",
    description = "HttpOnly JWT cookie authentication"
)
public class OpenApiConfig {
}
