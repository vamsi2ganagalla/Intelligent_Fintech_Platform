package com.fintech.auth.controller;

import com.fintech.auth.dto.AuthResponse;
import com.fintech.auth.dto.LoginRequest;
import com.fintech.auth.dto.RegisterRequest;
import com.fintech.auth.service.AuthService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.*;

@Slf4j
@RestController
@RequestMapping("/api/v1/auth")
@RequiredArgsConstructor
public class AuthController {

    private final AuthService authService;

    @PostMapping("/register")
    public String register(@Valid @RequestBody RegisterRequest request) {
        log.info("Registration request received for email: {}", request.getEmail());
        return authService.register(request);
    }

    @PostMapping("/login")
    public AuthResponse login(@Valid @RequestBody LoginRequest request) {
        log.info("Login request received for email: {}", request.getEmail());
        return authService.login(request);
    }

    @PostMapping("/refresh")
    public AuthResponse refresh(@RequestParam String refreshToken) {
        log.info("Token refresh request received");
        return authService.refreshAccessToken(refreshToken);
    }

    @PreAuthorize("hasRole('ADMIN')")
    @GetMapping("/admin")
    public String admin() {
        log.info("Admin endpoint accessed");
        return "Welcome Admin";
    }

    @PreAuthorize("hasRole('USER')")
    @GetMapping("/user")
    public String user() {
        log.info("User endpoint accessed");
        return "Welcome User";
    }
}