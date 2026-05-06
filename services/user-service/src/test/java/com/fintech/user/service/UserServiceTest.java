package com.fintech.user.service;

import com.fintech.user.dto.UpdateProfileRequest;
import com.fintech.user.dto.UserProfileResponse;
import com.fintech.user.entity.UserProfile;
import com.fintech.user.repository.UserProfileRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.time.LocalDateTime;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
@DisplayName("UserService Unit Tests")
class UserServiceTest {

    @Mock
    private UserProfileRepository userProfileRepository;

    @InjectMocks
    private UserService userService;

    private UserProfile existingProfile;

    @BeforeEach
    void setUp() {
        // Build a fully-formed profile, simulating what JPA does after @PrePersist
        existingProfile = UserProfile.builder()
                .id(1L)
                .email("test@fintech.com")
                .firstName("John")
                .lastName("Doe")
                .accountStatus(UserProfile.AccountStatus.ACTIVE)
                .createdAt(LocalDateTime.now().minusDays(1))
                .updatedAt(LocalDateTime.now().minusDays(1))
                .build();
    }

    @Test
    @DisplayName("getOrCreateProfile: should return existing profile when found")
    void getOrCreateProfile_whenProfileExists_shouldReturnIt() {
        // Given
        when(userProfileRepository.findByEmail("test@fintech.com"))
                .thenReturn(Optional.of(existingProfile));

        // When
        UserProfileResponse result = userService.getOrCreateProfile("test@fintech.com");

        // Then
        assertThat(result.getEmail()).isEqualTo("test@fintech.com");
        assertThat(result.getFirstName()).isEqualTo("John");
        verify(userProfileRepository, never()).save(any());
    }

    @Test
    @DisplayName("getOrCreateProfile: should create new profile when none exists")
    void getOrCreateProfile_whenProfileDoesNotExist_shouldCreate() {
        // Given
        when(userProfileRepository.findByEmail("new@fintech.com"))
                .thenReturn(Optional.empty());
        when(userProfileRepository.save(any(UserProfile.class)))
                .thenAnswer(invocation -> {
                    UserProfile saved = invocation.getArgument(0);
                    saved.setId(99L);
                    // Simulate what @PrePersist does — set the audit fields and default status
                    saved.setCreatedAt(LocalDateTime.now());
                    saved.setUpdatedAt(LocalDateTime.now());
                    saved.setAccountStatus(UserProfile.AccountStatus.ACTIVE);
                    return saved;
                });

        // When
        UserProfileResponse result = userService.getOrCreateProfile("new@fintech.com");

        // Then
        assertThat(result.getEmail()).isEqualTo("new@fintech.com");
        assertThat(result.getAccountStatus()).isEqualTo("ACTIVE");
        verify(userProfileRepository).save(any(UserProfile.class));
    }

    @Test
    @DisplayName("updateProfile: should partially update only provided fields")
    void updateProfile_shouldOnlyUpdateProvidedFields() {
        // Given
        UpdateProfileRequest request = new UpdateProfileRequest();
        request.setFirstName("Jane");  // only change firstName
        // lastName stays as "Doe", phoneNumber stays null

        when(userProfileRepository.findByEmail("test@fintech.com"))
                .thenReturn(Optional.of(existingProfile));
        when(userProfileRepository.save(any(UserProfile.class)))
                .thenAnswer(invocation -> invocation.getArgument(0));

        // When
        UserProfileResponse result = userService.updateProfile("test@fintech.com", request);

        // Then
        assertThat(result.getFirstName()).isEqualTo("Jane");      // changed
        assertThat(result.getLastName()).isEqualTo("Doe");        // unchanged
    }
}