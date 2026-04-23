package com.healthmate.config;

import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Configuration;
import org.springframework.core.Ordered;
import org.springframework.core.annotation.Order;
import org.springframework.web.servlet.config.annotation.ResourceHandlerRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

import java.nio.file.Path;
import java.nio.file.Paths;

@Slf4j
@Configuration
@Order(Ordered.HIGHEST_PRECEDENCE)
public class WebConfig implements WebMvcConfigurer {

    @Value("${healthmate.dataset-root:dataset/healthmate_2018-2023/data}")
    private String datasetRoot;

    @Override
    public void addResourceHandlers(ResourceHandlerRegistry registry) {
        Path root = Paths.get(datasetRoot).toAbsolutePath().normalize();
        Path assets = root.resolve("assets");
        Path img = root.resolve("img");

        String assetsLoc = "file:///" + assets.toString().replace("\\", "/") + "/";
        String imgLoc = "file:///" + img.toString().replace("\\", "/") + "/";

        registry.addResourceHandler(
                        "/healthmate/api/drugs/assets/**",
                        "/api/drugs/assets/**",
                        "/assets/**")
                .addResourceLocations(assetsLoc)
                .setCachePeriod(0);

        registry.addResourceHandler(
                        "/healthmate/api/drugs/img/**",
                        "/api/drugs/img/**",
                        "/img/**")
                .addResourceLocations(imgLoc)
                .setCachePeriod(0);
    }
}