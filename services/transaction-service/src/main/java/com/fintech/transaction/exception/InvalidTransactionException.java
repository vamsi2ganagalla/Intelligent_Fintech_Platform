package com.fintech.transaction.exception;

import org.springframework.http.HttpStatus;

public class InvalidTransactionException extends BusinessException {
    public InvalidTransactionException(String message) {
        super(message, HttpStatus.BAD_REQUEST);
    }
}