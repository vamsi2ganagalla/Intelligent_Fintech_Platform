package com.fintech.auth.service;

import com.fintech.auth.entity.RefreshToken;
import com.fintech.auth.entity.User;
import com.fintech.auth.exception.InvalidTokenException;
import com.fintech.auth.exception.TokenExpiredException;
import com.fintech.auth.repository.RefreshTokenRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.time.Instant;
import java.util.UUID;

@Slf4j
@Service
@RequiredArgsConstructor
public class RefreshTokenService {

    private final RefreshTokenRepository refreshTokenRepository;

    @Value("${jwt.refresh-expiration}")
    private long refreshExpiration;

    public RefreshToken createRefreshToken(User user) {
        RefreshToken token = RefreshToken.builder()
                .user(user)
                .token(UUID.randomUUID().toString())
                .expiryDate(Instant.now().plusMillis(refreshExpiration))
                .build();
        log.info("Refresh token created for user: {}", user.getEmail());
        return refreshTokenRepository.save(token);
    }

    public RefreshToken verifyToken(String token) {
        RefreshToken refreshToken = refreshTokenRepository.findByToken(token)
                .orElseThrow(() -> {
                    log.warn("Invalid refresh token presented");
                    return new InvalidTokenException("Invalid refresh token");
                });

        if (refreshToken.getExpiryDate().isBefore(Instant.now())) {
            refreshTokenRepository.delete(refreshToken);
            log.info("Expired refresh token deleted for user: {}",
                    refreshToken.getUser().getEmail());
            throw new TokenExpiredException("Refresh token has expired");
        }

        return refreshToken;
    }
}