package kz.cashguard.ml;

import java.nio.file.Path;
import java.util.List;
import org.springframework.http.MediaType;
import org.springframework.web.client.ResourceAccessException;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientResponseException;

public class MlClient {

    static final String INFER_PATH = "/infer";

    private final RestClient restClient;

    public MlClient(RestClient restClient) {
        this.restClient = restClient;
    }

    public List<MlEvent> infer(Path videoPath) {
        try {
            MlInferenceResponse response = restClient.post()
                    .uri(INFER_PATH)
                    .contentType(MediaType.APPLICATION_JSON)
                    .body(new MlInferenceRequest(videoPath.toAbsolutePath().toString()))
                    .retrieve()
                    .body(MlInferenceResponse.class);
            if (response == null || response.events() == null) {
                throw new MlUnavailableException("ML service returned an empty body", null);
            }
            return response.events();
        } catch (ResourceAccessException e) {
            throw new MlUnavailableException("ML service unreachable or timed out: " + e.getMessage(), e);
        } catch (RestClientResponseException e) {
            throw new MlUnavailableException("ML service responded " + e.getStatusCode() + ": " + e.getResponseBodyAsString(), e);
        }
    }
}
