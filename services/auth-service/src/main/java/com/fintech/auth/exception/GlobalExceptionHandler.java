package com.fintech.auth.exception;

import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.validation.FieldError;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

import java.time.LocalDateTime;
import java.util.HashMap;
import java.util.Map;

@Slf4j
@RestControllerAdvice
public class GlobalExceptionHandler {

    /**
     * Handles ALL business exceptions uniformly.
     * Each exception carries its own HttpStatus.
     */
    @ExceptionHandler(BusinessException.class)
    public ResponseEntity<?> handleBusinessException(BusinessException ex) {
        log.info("Business exception: {} -> {}", ex.getClass().getSimpleName(), ex.getMessage());
        return ResponseEntity
                .status(ex.getStatus())
                .body(Map.of(
                        "timestamp", LocalDateTime.now(),
                        "status", ex.getStatus().value(),
                        "error", ex.getStatus().getReasonPhrase(),
                        "message", ex.getMessage()
                ));
    }

    /**
     * Handles validation errors from @Valid annotations.
     */
    @ExceptionHandler(MethodArgumentNotValidException.class)
    public ResponseEntity<?> handleValidationErrors(MethodArgumentNotValidException ex) {
        Map<String, String> errors = new HashMap<>();
        ex.getBindingResult().getAllErrors().forEach(error -> {
            String field = ((FieldError) error).getField();
            String message = error.getDefaultMessage();
            errors.put(field, message);
        });
        return ResponseEntity
                .status(HttpStatus.BAD_REQUEST)
                .body(Map.of(
                        "timestamp", LocalDateTime.now(),
                        "status", HttpStatus.BAD_REQUEST.value(),
                        "error", "Validation Failed",
                        "errors", errors
                ));
    }

    /**
     * Catch-all for ANY unexpected exception (NPEs, DB failures, bugs, etc.)
     * - Logs the FULL stack trace internally for debugging
     * - Returns a GENERIC message to the client (never leaks internals)
     */
    @ExceptionHandler(Exception.class)
    public ResponseEntity<?> handleGeneral(Exception ex) {
        log.error("Unexpected exception caught by global handler", ex);
        return ResponseEntity
                .status(HttpStatus.INTERNAL_SERVER_ERROR)
                .body(Map.of(
                        "timestamp", LocalDateTime.now(),
                        "status", HttpStatus.INTERNAL_SERVER_ERROR.value(),
                        "error", "Internal Server Error",
                        "message", "An unexpected error occurred. Please try again later."
                ));
    }
}