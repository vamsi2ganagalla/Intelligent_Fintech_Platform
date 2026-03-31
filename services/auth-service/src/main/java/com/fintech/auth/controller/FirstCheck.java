package com.fintech.auth.controller;

import com.fintech.auth.dto.RegisterRequest;
import com.fintech.auth.service.AuthService;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/auth")
@RequiredArgsConstructor
public class FirstCheck {

    private final AuthService authService;

    @GetMapping("/test")
    public String check(){
        return "Auth service is Working";
    }

    @PostMapping("/register")
    public String register(@RequestBody RegisterRequest request){
        return authService.register(request);
    }
}