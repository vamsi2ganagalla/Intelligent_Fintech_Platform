package com.fintech.auth.exception;

import org.springframework.http.HttpStatus;

public class InvalidCredentialsException extends BusinessException {
    public InvalidCredentialsException(String message) {
        super(message, HttpStatus.UNAUTHORIZED);
    }
}