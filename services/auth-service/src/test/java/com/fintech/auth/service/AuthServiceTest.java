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
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;

import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
@DisplayName("AuthService Unit Tests")
class AuthServiceTest {

    @Mock
    private UserRepository userRepository;

    @Mock
    private BCryptPasswordEncoder passwordEncoder;

    @Mock
    private JwtUtil jwtUtil;

    @Mock
    private RefreshTokenService refreshTokenService;

    @InjectMocks
    private AuthService authService;

    private RegisterRequest registerRequest;
    private LoginRequest loginRequest;
    private User existingUser;

    @BeforeEach
    void setUp() {
        registerRequest = new RegisterRequest();
        registerRequest.setEmail("test@fintech.com");
        registerRequest.setPassword("Test1234!");

        loginRequest = new LoginRequest();
        loginRequest.setEmail("test@fintech.com");
        loginRequest.setPassword("Test1234!");

        existingUser = User.builder()
                .id(1L)
                .email("test@fintech.com")
                .password("$2a$10$hashedPasswordValue")
                .role("ROLE_USER")
                .build();
    }

    @Test
    @DisplayName("register: should successfully register a new user")
    void register_whenEmailNotTaken_shouldRegisterUser() {
        // Given
        when(userRepository.findByEmail("test@fintech.com")).thenReturn(Optional.empty());
        when(passwordEncoder.encode("Test1234!")).thenReturn("$2a$10$hashedPasswordValue");

        // When
        String result = authService.register(registerRequest);

        // Then
        assertThat(result).isEqualTo("User registered successfully");
        verify(userRepository).save(any(User.class));
    }

    @Test
    @DisplayName("register: should throw UserAlreadyExistsException when email is taken")
    void register_whenEmailExists_shouldThrowUserAlreadyExistsException() {
        // Given
        when(userRepository.findByEmail("test@fintech.com"))
                .thenReturn(Optional.of(existingUser));

        // When / Then
        assertThatThrownBy(() -> authService.register(registerRequest))
                .isInstanceOf(UserAlreadyExistsException.class)
                .hasMessageContaining("already exists");

        verify(userRepository, never()).save(any(User.class));
    }

    @Test
    @DisplayName("login: should return tokens when credentials are valid")
    void login_whenCredentialsValid_shouldReturnAuthResponse() {
        // Given
        when(userRepository.findByEmail("test@fintech.com"))
                .thenReturn(Optional.of(existingUser));
        when(passwordEncoder.matches("Test1234!", "$2a$10$hashedPasswordValue"))
                .thenReturn(true);
        when(jwtUtil.generateToken("test@fintech.com", "ROLE_USER"))
                .thenReturn("mocked-access-token");

        RefreshToken mockRefreshToken = RefreshToken.builder()
                .token("mocked-refresh-token")
                .user(existingUser)
                .build();
        when(refreshTokenService.createRefreshToken(existingUser))
                .thenReturn(mockRefreshToken);

        // When
        AuthResponse response = authService.login(loginRequest);

        // Then
        assertThat(response).isNotNull();
        assertThat(response.getAccessToken()).isEqualTo("mocked-access-token");
        assertThat(response.getRefreshToken()).isEqualTo("mocked-refresh-token");
    }

    @Test
    @DisplayName("login: should throw InvalidCredentialsException when password is wrong")
    void login_whenPasswordWrong_shouldThrowInvalidCredentialsException() {
        // Given
        when(userRepository.findByEmail("test@fintech.com"))
                .thenReturn(Optional.of(existingUser));
        when(passwordEncoder.matches(anyString(), anyString())).thenReturn(false);

        // When / Then
        assertThatThrownBy(() -> authService.login(loginRequest))
                .isInstanceOf(InvalidCredentialsException.class)
                .hasMessageContaining("Invalid email or password");

        // Verify no token was generated
        verify(jwtUtil, never()).generateToken(anyString(), anyString());
    }

    @Test
    @DisplayName("login: should throw InvalidCredentialsException when email not found")
    void login_whenEmailNotFound_shouldThrowInvalidCredentialsException() {
        // Given
        when(userRepository.findByEmail("test@fintech.com")).thenReturn(Optional.empty());

        // When / Then
        // Critical: same exception type as wrong-password (username enumeration prevention)
        assertThatThrownBy(() -> authService.login(loginRequest))
                .isInstanceOf(InvalidCredentialsException.class)
                .hasMessageContaining("Invalid email or password");
    }
}