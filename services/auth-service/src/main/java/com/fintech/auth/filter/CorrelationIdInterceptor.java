package com.fintech.auth.filter;

import jakarta.servlet.http.HttpServletRequest;
import org.slf4j.MDC;
import org.springframework.http.HttpRequest;
import org.springframework.http.client.ClientHttpRequestExecution;
import org.springframework.http.client.ClientHttpRequestInterceptor;
import org.springframework.http.client.ClientHttpResponse;
import org.springframework.stereotype.Component;
import org.springframework.web.context.request.RequestContextHolder;
import org.springframework.web.context.request.ServletRequestAttributes;

import java.io.IOException;

/**
 * Phase 6.5 — Outbound correlation ID propagation.
 *
 * Attached to the RestTemplate bean below. Every outbound HTTP call made via
 * RestTemplate will carry X-Correlation-Id, sourced from MDC (set by
 * CorrelationIdFilter for the current inbound request).
 *
 * Fallback chain:
 *  1. MDC value (correlationId) — present during a live inbound request
 *  2. Incoming request header — direct read if MDC was cleared
 *  3. "no-correlation-id" — sentinel so the header is always present
 */
@Component
public class CorrelationIdInterceptor implements ClientHttpRequestInterceptor {

    private static final String HEADER  = "X-Correlation-Id";
    private static final String MDC_KEY = "correlationId";

    @Override
    public ClientHttpResponse intercept(HttpRequest request,
                                        byte[] body,
                                        ClientHttpRequestExecution execution)
            throws IOException {

        String correlationId = MDC.get(MDC_KEY);

        if (correlationId == null || correlationId.isBlank()) {
            // Fallback: read from current servlet request if MDC was already cleared
            ServletRequestAttributes attrs =
                    (ServletRequestAttributes) RequestContextHolder.getRequestAttributes();
            if (attrs != null) {
                HttpServletRequest servletRequest = attrs.getRequest();
                correlationId = servletRequest.getHeader(HEADER);
            }
        }

        if (correlationId == null || correlationId.isBlank()) {
            correlationId = "no-correlation-id";
        }

        request.getHeaders().set(HEADER, correlationId);
        return execution.execute(request, body);
    }
}
