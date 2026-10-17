package kz.cashguard.config;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.boot.web.servlet.FilterRegistrationBean;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.core.Ordered;

@Configuration
public class SecurityConfig {

    @Bean
    public FilterRegistrationBean<ApiKeyFilter> apiKeyFilter(AppProperties properties, ObjectMapper objectMapper) {
        var registration = new FilterRegistrationBean<>(new ApiKeyFilter(properties.apiKey(), objectMapper));
        registration.addUrlPatterns(ApiKeyFilter.PROTECTED_PREFIX + "*");
        registration.setOrder(Ordered.HIGHEST_PRECEDENCE);
        return registration;
    }
}
