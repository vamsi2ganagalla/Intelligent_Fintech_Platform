package com.fintech.user.service;

import com.fintech.user.dto.UpdateProfileRequest;
import com.fintech.user.dto.UserProfileResponse;
import com.fintech.user.entity.UserProfile;
import com.fintech.user.repository.UserProfileRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

@Slf4j
@Service
@RequiredArgsConstructor
public class UserService {

    private final UserProfileRepository userProfileRepository;

    public UserProfileResponse getOrCreateProfile(String email) {
        UserProfile profile = userProfileRepository.findByEmail(email)
                .orElseGet(() -> createEmptyProfile(email));
        return UserProfileResponse.fromEntity(profile);
    }

    public UserProfileResponse updateProfile(String email,
                                             UpdateProfileRequest request) {
        UserProfile profile = userProfileRepository.findByEmail(email)
                .orElseGet(() -> createEmptyProfile(email));

        if (request.getFirstName() != null)
            profile.setFirstName(request.getFirstName());
        if (request.getLastName() != null)
            profile.setLastName(request.getLastName());
        if (request.getPhoneNumber() != null)
            profile.setPhoneNumber(request.getPhoneNumber());
        if (request.getDateOfBirth() != null)
            profile.setDateOfBirth(request.getDateOfBirth());
        if (request.getAddress() != null)
            profile.setAddress(request.getAddress());

        UserProfile saved = userProfileRepository.save(profile);
        log.info("Profile updated for user: {}", email);
        return UserProfileResponse.fromEntity(saved);
    }

    private UserProfile createEmptyProfile(String email) {
        UserProfile profile = UserProfile.builder()
                .email(email)
                .build();
        return userProfileRepository.save(profile);
    }
}