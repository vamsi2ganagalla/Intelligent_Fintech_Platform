package com.fintech.auth.service;

import com.fintech.auth.dto.AuthResponse;
import com.fintech.auth.dto.LoginRequest;
import com.fintech.auth.dto.RegisterRequest;
import com.fintech.auth.entity.RefreshToken;
import com.fintech.auth.entity.User;
import com.fintech.auth.exception.InvalidCredentialsException;
import com.fintech.auth.exception.UserAlreadyExistsException;
import com.fintech.auth.repository.UserRepository;
import com.fintech.auth.security.JwtUtil;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.stereotype.Service;

@Slf4j
@Service
@RequiredArgsConstructor
public class AuthService {

    private final UserRepository userRepository;
    private final BCryptPasswordEncoder passwordEncoder;
    private final JwtUtil jwtUtil;
    private final RefreshTokenService refreshTokenService;

    public String register(RegisterRequest request) {

        if (userRepository.findByEmail(request.getEmail()).isPresent()) {
            log.warn("Registration attempt with existing email: {}", request.getEmail());
            throw new UserAlreadyExistsException("User with this email already exists");
        }

        String hashedPassword = passwordEncoder.encode(request.getPassword());

        User user = User.builder()
                .email(request.getEmail())
                .password(hashedPassword)
                .role("ROLE_USER")
                .build();

        userRepository.save(user);
        log.info("User registered: {}", request.getEmail());

        return "User registered successfully";
    }

    public AuthResponse login(LoginRequest request) {

        User user = userRepository.findByEmail(request.getEmail())
                .orElseThrow(() -> {
                    log.warn("Login attempt with unknown email: {}", request.getEmail());
                    return new InvalidCredentialsException("Invalid email or password");
                });

        if (!passwordEncoder.matches(request.getPassword(), user.getPassword())) {
            log.warn("Login attempt with wrong password for email: {}", request.getEmail());
            throw new InvalidCredentialsException("Invalid email or password");
        }

        String accessToken = jwtUtil.generateToken(user.getEmail(), user.getRole());
        String refreshToken = refreshTokenService.createRefreshToken(user).getToken();

        log.info("User logged in: {}", request.getEmail());
        return new AuthResponse(accessToken, refreshToken);
    }

    public AuthResponse refreshAccessToken(String refreshToken) {
        RefreshToken token = refreshTokenService.verifyToken(refreshToken);
        User user = token.getUser();
        String newAccessToken = jwtUtil.generateToken(user.getEmail(), user.getRole());
        log.info("Access token refreshed for user: {}", user.getEmail());
        return new AuthResponse(newAccessToken, refreshToken);
    }
}