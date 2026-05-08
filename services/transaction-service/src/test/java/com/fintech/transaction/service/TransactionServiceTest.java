package com.fintech.transaction.service;

import com.fintech.transaction.dto.TransactionRequest;
import com.fintech.transaction.dto.TransactionResponse;
import com.fintech.transaction.entity.Transaction;
import com.fintech.transaction.entity.TransactionStatus;
import com.fintech.transaction.entity.TransactionType;
import com.fintech.transaction.exception.TransactionNotFoundException;
import com.fintech.transaction.repository.TransactionRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.Collections;
import java.util.List;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
@DisplayName("TransactionService Unit Tests")
class TransactionServiceTest {

    @Mock
    private TransactionRepository transactionRepository;

    @InjectMocks
    private TransactionService transactionService;

    private TransactionRequest validRequest;
    private Transaction sampleTransaction;
    private final String userEmail = "test@fintech.com";

    @BeforeEach
    void setUp() {
        validRequest = new TransactionRequest();
        validRequest.setAmount(new BigDecimal("100.50"));
        validRequest.setType(TransactionType.CREDIT);
        validRequest.setDescription("Test transaction");

        sampleTransaction = Transaction.builder()
                .id(1L)
                .userEmail(userEmail)
                .amount(new BigDecimal("100.50"))
                .type(TransactionType.CREDIT)
                .description("Test transaction")
                .status(TransactionStatus.COMPLETED)
                .createdAt(LocalDateTime.now())
                .updatedAt(LocalDateTime.now())
                .build();
    }

    @Test
    @DisplayName("createTransaction: should successfully create and persist a transaction")
    void createTransaction_shouldPersistAndReturn() {
        // Given
        when(transactionRepository.save(any(Transaction.class)))
                .thenAnswer(invocation -> {
                    Transaction t = invocation.getArgument(0);
                    t.setId(1L);
                    t.setCreatedAt(LocalDateTime.now());
                    t.setUpdatedAt(LocalDateTime.now());
                    if (t.getStatus() == null) {
                        t.setStatus(TransactionStatus.COMPLETED);
                    }
                    return t;
                });

        // When
        TransactionResponse response = transactionService.createTransaction(userEmail, validRequest);

        // Then
        assertThat(response).isNotNull();
        assertThat(response.getUserEmail()).isEqualTo(userEmail);
        assertThat(response.getAmount()).isEqualByComparingTo(new BigDecimal("100.50"));
        assertThat(response.getType()).isEqualTo(TransactionType.CREDIT);
        assertThat(response.getStatus()).isEqualTo(TransactionStatus.COMPLETED);
        verify(transactionRepository).save(any(Transaction.class));
    }

    @Test
    @DisplayName("getUserTransactions: should return list of transactions for user")
    void getUserTransactions_whenTransactionsExist_shouldReturnList() {
        // Given
        when(transactionRepository.findByUserEmailOrderByCreatedAtDesc(userEmail))
                .thenReturn(List.of(sampleTransaction));

        // When
        List<TransactionResponse> result = transactionService.getUserTransactions(userEmail);

        // Then
        assertThat(result).hasSize(1);
        assertThat(result.get(0).getUserEmail()).isEqualTo(userEmail);
        assertThat(result.get(0).getAmount()).isEqualByComparingTo(new BigDecimal("100.50"));
    }

    @Test
    @DisplayName("getUserTransactions: should return empty list when no transactions exist")
    void getUserTransactions_whenNoTransactions_shouldReturnEmptyList() {
        // Given
        when(transactionRepository.findByUserEmailOrderByCreatedAtDesc(userEmail))
                .thenReturn(Collections.emptyList());

        // When
        List<TransactionResponse> result = transactionService.getUserTransactions(userEmail);

        // Then
        assertThat(result).isEmpty();
    }

    @Test
    @DisplayName("getTransaction: should return transaction when ID matches and user owns it")
    void getTransaction_whenOwnedByUser_shouldReturnTransaction() {
        // Given
        when(transactionRepository.findByIdAndUserEmail(1L, userEmail))
                .thenReturn(Optional.of(sampleTransaction));

        // When
        TransactionResponse response = transactionService.getTransaction(userEmail, 1L);

        // Then
        assertThat(response.getId()).isEqualTo(1L);
        assertThat(response.getUserEmail()).isEqualTo(userEmail);
    }

    /**
     * THIS IS THE CRITICAL SECURITY TEST.
     * It mirrors the IDOR-prevention test we did manually in Swagger.
     * If a future refactor accidentally uses findById(id) instead of findByIdAndUserEmail(id, user),
     * this test will catch it — even if the refactor "works" superficially.
     */
    @Test
    @DisplayName("getTransaction: should throw TransactionNotFoundException for cross-user access (IDOR prevention)")
    void getTransaction_whenAccessedByDifferentUser_shouldThrowNotFoundException() {
        // Given - the repository correctly returns empty when the user doesn't own the transaction
        String attackerEmail = "attacker@fintech.com";
        when(transactionRepository.findByIdAndUserEmail(1L, attackerEmail))
                .thenReturn(Optional.empty());

        // When / Then
        assertThatThrownBy(() -> transactionService.getTransaction(attackerEmail, 1L))
                .isInstanceOf(TransactionNotFoundException.class)
                .hasMessageContaining("Transaction not found with id: 1");
    }
}