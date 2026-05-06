package com.fintech.transaction.repository;

import com.fintech.transaction.entity.Transaction;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.repository.query.Param;
import org.springframework.data.jpa.repository.Query;

import java.util.List;
import java.util.Optional;

public interface TransactionRepository extends JpaRepository<Transaction, Long> {

    /**
     * Find all transactions for a given user, most recent first.
     */
    List<Transaction> findByUserEmailOrderByCreatedAtDesc(String userEmail);

    /**
     * Find a specific transaction belonging to a specific user.
     * Used for authorization — a user should only access their own transactions.
     */
    Optional<Transaction> findByIdAndUserEmail(Long id, String userEmail);

    /**
     * Count all transactions for a user.
     */
    long countByUserEmail(String userEmail);
}