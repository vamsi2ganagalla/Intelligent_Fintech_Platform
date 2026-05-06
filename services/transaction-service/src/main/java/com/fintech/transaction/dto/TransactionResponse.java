package com.fintech.transaction.dto;

import com.fintech.transaction.entity.Transaction;
import com.fintech.transaction.entity.TransactionStatus;
import com.fintech.transaction.entity.TransactionType;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.math.BigDecimal;
import java.time.LocalDateTime;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class TransactionResponse {

    private Long id;
    private String userEmail;
    private BigDecimal amount;
    private TransactionType type;
    private String description;
    private TransactionStatus status;
    private LocalDateTime createdAt;
    private LocalDateTime updatedAt;

    /**
     * Static factory for converting entity → response DTO.
     * Centralizes the conversion logic — when entity changes, only this method updates.
     */
    public static TransactionResponse fromEntity(Transaction transaction) {
        return TransactionResponse.builder()
                .id(transaction.getId())
                .userEmail(transaction.getUserEmail())
                .amount(transaction.getAmount())
                .type(transaction.getType())
                .description(transaction.getDescription())
                .status(transaction.getStatus())
                .createdAt(transaction.getCreatedAt())
                .updatedAt(transaction.getUpdatedAt())
                .build();
    }
}