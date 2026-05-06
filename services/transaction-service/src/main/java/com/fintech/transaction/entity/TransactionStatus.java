package com.fintech.transaction.entity;

public enum TransactionStatus {
    PENDING,     // recorded but not yet processed
    COMPLETED,   // success
    FAILED       // processing error
}