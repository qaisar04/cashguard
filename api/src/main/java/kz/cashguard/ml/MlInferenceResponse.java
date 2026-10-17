package kz.cashguard.ml;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import java.util.List;

@JsonIgnoreProperties(ignoreUnknown = true)
public record MlInferenceResponse(List<MlEvent> events) {
}
