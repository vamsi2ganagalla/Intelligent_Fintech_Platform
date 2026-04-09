package com.fintech.auth.security;

import io.jsonwebtoken.Claims;
import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.SignatureAlgorithm;
import io.jsonwebtoken.security.Keys;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import java.security.Key;
import java.util.Date;

@Component
public class JwtUtil {

    @Value("${jwt.secret}")
    private String secret;

    @Value("${jwt.expiration}")
    private long expiration;

    // 🔐 Generate signing key
    private Key getKey() {
        return Keys.hmacShaKeyFor(secret.getBytes());
    }

    // 🔥 Generate JWT Token
    public String generateToken(String email, String role) {
        return Jwts.builder()
                .setSubject(email)
                .claim("role", role)
                .setIssuedAt(new Date())
                .setExpiration(new Date(System.currentTimeMillis() + expiration))
                .signWith(getKey(), SignatureAlgorithm.HS256)
                .compact();
    }

    // 🔍 Extract all claims
    private Claims extractClaims(String token) {
        return Jwts.parserBuilder()
                .setSigningKey(getKey())
                .build()
                .parseClaimsJws(token)
                .getBody();
    }

    // 🔍 Extract email
    public String extractEmail(String token) {
        return extractClaims(token).getSubject();
    }

    // 🔍 Extract role
    public String extractRole(String token) {
        return extractClaims(token).get("role", String.class);
    }

    // ✅ Validate token (including expiry)
    public boolean isTokenValid(String token) {
        try {
            Claims claims = extractClaims(token);
            Date expirationDate = claims.getExpiration();

            return expirationDate.after(new Date()); // 🔥 expiry check

        } catch (Exception e) {
            return false;
        }
    }
}