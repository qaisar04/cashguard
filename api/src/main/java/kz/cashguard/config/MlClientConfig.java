package kz.cashguard.config;

import java.net.http.HttpClient;
import java.time.Duration;
import kz.cashguard.ml.MlClient;
import org.springframework.boot.http.client.ClientHttpRequestFactoryBuilder;
import org.springframework.boot.http.client.ClientHttpRequestFactorySettings;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.client.RestClient;

@Configuration
public class MlClientConfig {

    private static final Duration CONNECT_TIMEOUT = Duration.ofSeconds(5);

    @Bean
    public RestClient mlRestClient(AppProperties properties) {
        var settings = ClientHttpRequestFactorySettings.defaults()
                .withConnectTimeout(CONNECT_TIMEOUT)
                .withReadTimeout(properties.ml().timeout());
        return RestClient.builder()
                .baseUrl(properties.ml().baseUrl())
                .defaultHeader(ApiKeyFilter.HEADER, properties.ml().apiKey())
                .requestFactory(ClientHttpRequestFactoryBuilder.jdk()
                        // uvicorn ignores the body of an "Upgrade: h2c" request, which the JDK client sends by default
                        .withHttpClientCustomizer(builder -> builder.version(HttpClient.Version.HTTP_1_1))
                        .build(settings))
                .build();
    }

    @Bean
    public MlClient mlClient(RestClient mlRestClient) {
        return new MlClient(mlRestClient);
    }
}
