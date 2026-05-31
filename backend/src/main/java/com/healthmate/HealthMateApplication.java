package com.healthmate;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.scheduling.annotation.EnableScheduling;
import org.springframework.modulith.Modulithic;

@SpringBootApplication
@EnableScheduling
@Modulithic(sharedModules = {"common", "config", "exception"})
public class HealthMateApplication {
    public static void main(String[] args) {
        SpringApplication.run(HealthMateApplication.class, args);
    }
}