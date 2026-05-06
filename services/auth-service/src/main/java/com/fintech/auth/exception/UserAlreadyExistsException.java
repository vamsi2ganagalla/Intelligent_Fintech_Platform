package com.fintech.auth.exception;

import org.springframework.http.HttpStatus;

public class UserAlreadyExistsException extends BusinessException {
    public UserAlreadyExistsException(String message) {
        super(message, HttpStatus.CONFLICT);
    }
}