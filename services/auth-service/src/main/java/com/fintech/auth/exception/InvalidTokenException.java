package com.fintech.auth.exception;

import org.springframework.http.HttpStatus;

public class InvalidTokenException extends BusinessException {
    public InvalidTokenException(String message) {
        super(message, HttpStatus.UNAUTHORIZED);
    }
}