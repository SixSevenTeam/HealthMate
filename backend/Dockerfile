# syntax=docker/dockerfile:1

FROM maven:3.9.9-eclipse-temurin-17 AS build
WORKDIR /build

COPY pom.xml .
COPY src ./src

RUN mvn -DskipTests clean package

FROM eclipse-temurin:17-jre-alpine
WORKDIR /app

COPY --from=build /build/target/healthmate-backend-1.0.0.jar app.jar

EXPOSE 8080

ENTRYPOINT ["java", "-jar", "/app/app.jar"]
