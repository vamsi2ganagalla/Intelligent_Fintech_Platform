package com.fintech.auth.config;

import com.fintech.auth.filter.CorrelationIdInterceptor;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.client.RestTemplate;

import java.util.List;

/**
 * Phase 6.5 — RestTemplate with correlation ID propagation.
 *
 * Any @Autowired RestTemplate in this service will automatically forward
 * X-Correlation-Id on every outbound HTTP request.
 */
@Configuration
public class RestTemplateConfig {

    @Bean
    public RestTemplate restTemplate(CorrelationIdInterceptor correlationIdInterceptor) {
        RestTemplate restTemplate = new RestTemplate();
        restTemplate.setInterceptors(List.of(correlationIdInterceptor));
        return restTemplate;
    }
}
