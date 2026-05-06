package com.fintech.auth.service;

import com.fintech.auth.entity.RefreshToken;
import com.fintech.auth.entity.User;
import com.fintech.auth.exception.InvalidTokenException;
import com.fintech.auth.exception.TokenExpiredException;
import com.fintech.auth.repository.RefreshTokenRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.test.util.ReflectionTestUtils;

import java.time.Instant;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
@DisplayName("RefreshTokenService Unit Tests")
class RefreshTokenServiceTest {

    @Mock
    private RefreshTokenRepository refreshTokenRepository;

    @InjectMocks
    private RefreshTokenService refreshTokenService;

    private User testUser;

    @BeforeEach
    void setUp() {
        // Inject the @Value-annotated field manually — Mockito doesn't read application.yaml
        ReflectionTestUtils.setField(refreshTokenService, "refreshExpiration", 604800000L);

        testUser = User.builder()
                .id(1L)
                .email("test@fintech.com")
                .password("hashed")
                .role("ROLE_USER")
                .build();
    }

    @Test
    @DisplayName("verifyToken: should throw InvalidTokenException when token not found")
    void verifyToken_whenTokenNotFound_shouldThrowInvalidTokenException() {
        // Given
        when(refreshTokenRepository.findByToken("nonexistent-token"))
                .thenReturn(Optional.empty());

        // When / Then
        assertThatThrownBy(() -> refreshTokenService.verifyToken("nonexistent-token"))
                .isInstanceOf(InvalidTokenException.class)
                .hasMessageContaining("Invalid refresh token");
    }

    @Test
    @DisplayName("verifyToken: should throw TokenExpiredException and delete expired token")
    void verifyToken_whenTokenExpired_shouldThrowAndDeleteToken() {
        // Given - a token expired 1 hour ago
        RefreshToken expiredToken = RefreshToken.builder()
                .id(1L)
                .token("expired-token")
                .user(testUser)
                .expiryDate(Instant.now().minusSeconds(3600))
                .build();

        when(refreshTokenRepository.findByToken("expired-token"))
                .thenReturn(Optional.of(expiredToken));

        // When / Then
        assertThatThrownBy(() -> refreshTokenService.verifyToken("expired-token"))
                .isInstanceOf(TokenExpiredException.class)
                .hasMessageContaining("expired");

        // Critical: verify the expired token was cleaned up
        verify(refreshTokenRepository).delete(expiredToken);
    }

    @Test
    @DisplayName("verifyToken: should return token when valid and not expired")
    void verifyToken_whenTokenValid_shouldReturnToken() {
        // Given - a token expiring 1 hour in the future
        RefreshToken validToken = RefreshToken.builder()
                .id(1L)
                .token("valid-token")
                .user(testUser)
                .expiryDate(Instant.now().plusSeconds(3600))
                .build();

        when(refreshTokenRepository.findByToken("valid-token"))
                .thenReturn(Optional.of(validToken));

        // When
        RefreshToken result = refreshTokenService.verifyToken("valid-token");

        // Then
        assertThat(result).isEqualTo(validToken);
        assertThat(result.getUser()).isEqualTo(testUser);
    }

    @Test
    @DisplayName("createRefreshToken: should generate UUID-format token with future expiry")
    void createRefreshToken_shouldGenerateUuidAndSetExpiry() {
        // Given
        when(refreshTokenRepository.save(any(RefreshToken.class)))
                .thenAnswer(invocation -> invocation.getArgument(0));

        // When
        RefreshToken result = refreshTokenService.createRefreshToken(testUser);

        // Then
        assertThat(result.getToken()).isNotBlank();
        assertThat(result.getToken()).hasSize(36); // UUID format
        assertThat(result.getUser()).isEqualTo(testUser);
        assertThat(result.getExpiryDate()).isAfter(Instant.now());
    }
}