# ============================================================
# STAGE 1: Build the JAR using Maven + JDK
# ============================================================
FROM eclipse-temurin:17-jdk-jammy AS builder

WORKDIR /build

# Copy Maven wrapper + pom.xml FIRST (for layer caching)
COPY .mvn .mvn
COPY mvnw pom.xml ./
RUN chmod +x mvnw

# Pre-download dependencies (cached if pom.xml hasn't changed)
RUN ./mvnw dependency:go-offline -B

# Copy source code (changes most often, so it's last)
COPY src ./src

# Build the JAR (skipping tests — we run those separately in CI)
RUN ./mvnw clean package -DskipTests -B

# ============================================================
# STAGE 2: Runtime image (JRE only, no build tools)
# ============================================================
FROM eclipse-temurin:17-jre-jammy

# Create a non-root user for security
RUN groupadd --system --gid 1001 appuser && \
    useradd --system --uid 1001 --gid appuser --shell /bin/false appuser

WORKDIR /app

# Copy ONLY the built JAR from the builder stage
COPY --from=builder /build/target/*.jar app.jar

# Drop root privileges
USER appuser

# Document the port (informational only — actual port mapping happens at runtime)
EXPOSE 8081

# Health check (uses Actuator endpoint we set up on Day 0!)
HEALTHCHECK --interval=30s --timeout=3s --start-period=40s --retries=3 \
    CMD wget -qO- http://localhost:8081/actuator/health/liveness || exit 1

# Run the JAR
ENTRYPOINT ["java", "-jar", "/app/app.jar"]
