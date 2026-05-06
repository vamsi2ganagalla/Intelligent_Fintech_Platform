package com.fintech.transaction.controller;

import com.fintech.transaction.dto.TransactionRequest;
import com.fintech.transaction.dto.TransactionResponse;
import com.fintech.transaction.service.TransactionService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@Slf4j
@RestController
@RequestMapping("/api/v1/transactions")
@RequiredArgsConstructor
public class TransactionController {

    private final TransactionService transactionService;

    @PostMapping
    public ResponseEntity<TransactionResponse> createTransaction(
            @AuthenticationPrincipal String userEmail,
            @Valid @RequestBody TransactionRequest request) {

        log.info("Create transaction request received from user: {}", userEmail);

        TransactionResponse response = transactionService.createTransaction(userEmail, request);
        return ResponseEntity.status(HttpStatus.CREATED).body(response);
    }

    @GetMapping
    public ResponseEntity<List<TransactionResponse>> getUserTransactions(
            @AuthenticationPrincipal String userEmail) {

        log.info("List transactions request received from user: {}", userEmail);

        List<TransactionResponse> transactions = transactionService.getUserTransactions(userEmail);
        return ResponseEntity.ok(transactions);
    }

    @GetMapping("/{id}")
    public ResponseEntity<TransactionResponse> getTransaction(
            @AuthenticationPrincipal String userEmail,
            @PathVariable Long id) {

        log.info("Get transaction request received: id={}, user={}", id, userEmail);

        TransactionResponse response = transactionService.getTransaction(userEmail, id);
        return ResponseEntity.ok(response);
    }
}