package com.fintech.user.dto;

import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;
import lombok.Data;
import java.time.LocalDate;

@Data
public class UpdateProfileRequest {

    @Size(min = 2, message = "First name must be at least 2 characters")
    private String firstName;

    @Size(min = 2, message = "Last name must be at least 2 characters")
    private String lastName;

    @Pattern(regexp = "^[+]?[0-9]{10,13}$", message = "Invalid phone number")
    private String phoneNumber;

    private LocalDate dateOfBirth;

    private String address;
}