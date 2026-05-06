package com.fintech.transaction.service;

import com.fintech.transaction.dto.TransactionRequest;
import com.fintech.transaction.dto.TransactionResponse;
import com.fintech.transaction.entity.Transaction;
import com.fintech.transaction.entity.TransactionStatus;
import com.fintech.transaction.exception.TransactionNotFoundException;
import com.fintech.transaction.repository.TransactionRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

@Slf4j
@Service
@RequiredArgsConstructor
public class TransactionService {

    private final TransactionRepository transactionRepository;

    /**
     * Creates a new transaction for the authenticated user.
     * The userEmail comes from the JWT, not from the request body.
     */
    @Transactional
    public TransactionResponse createTransaction(String userEmail, TransactionRequest request) {
        Transaction transaction = Transaction.builder()
                .userEmail(userEmail)
                .amount(request.getAmount())
                .type(request.getType())
                .description(request.getDescription())
                .status(TransactionStatus.COMPLETED)
                .build();

        Transaction saved = transactionRepository.save(transaction);
        log.info("Transaction created: id={}, user={}, amount={}, type={}",
                saved.getId(), userEmail, saved.getAmount(), saved.getType());

        return TransactionResponse.fromEntity(saved);
    }

    /**
     * Lists all transactions for the authenticated user, most recent first.
     */
    @Transactional(readOnly = true)
    public List<TransactionResponse> getUserTransactions(String userEmail) {
        List<Transaction> transactions = transactionRepository
                .findByUserEmailOrderByCreatedAtDesc(userEmail);

        log.info("Fetched {} transactions for user: {}", transactions.size(), userEmail);

        return transactions.stream()
                .map(TransactionResponse::fromEntity)
                .toList();
    }

    /**
     * Fetches a single transaction by ID — but ONLY if it belongs to the requesting user.
     * Returns 404 even if the transaction exists but belongs to someone else.
     * This is deliberate IDOR-prevention.
     */
    @Transactional(readOnly = true)
    public TransactionResponse getTransaction(String userEmail, Long id) {
        Transaction transaction = transactionRepository
                .findByIdAndUserEmail(id, userEmail)
                .orElseThrow(() -> {
                    log.warn("Transaction lookup failed: id={}, user={}", id, userEmail);
                    return new TransactionNotFoundException(
                            "Transaction not found with id: " + id);
                });

        return TransactionResponse.fromEntity(transaction);
    }
}