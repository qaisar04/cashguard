package kz.cashguard.config;

import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import java.time.Duration;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.util.unit.DataSize;
import org.springframework.validation.annotation.Validated;

@Validated
@ConfigurationProperties(prefix = "cashguard")
public record AppProperties(
        @NotBlank String apiKey,
        @NotNull Ml ml,
        @NotNull Storage storage,
        @NotNull Job job) {

    public record Ml(@NotBlank String baseUrl, @NotBlank String apiKey, @NotNull Duration timeout) {
    }

    public record Storage(@NotBlank String dir, @NotNull DataSize maxUpload) {
    }

    public record Job(@Min(1) int workers, @Min(1) int queueCapacity, @NotNull Duration ttl) {
    }
}
