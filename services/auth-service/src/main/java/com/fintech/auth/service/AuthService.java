package com.fintech.auth.service;

import com.fintech.auth.dto.RegisterRequest;
import com.fintech.auth.entity.User;
import com.fintech.auth.repository.UserRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

@Service
@RequiredArgsConstructor
public class AuthService {

    private final UserRepository userRepository;

    public String register(RegisterRequest request) {

        User user = User.builder()
                .email(request.getEmail())
                .password(request.getPassword()) // (we will hash later)
                .build();

        userRepository.save(user);

        return "User registered successfully";
    }
}