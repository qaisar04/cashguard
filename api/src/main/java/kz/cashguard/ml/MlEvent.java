package kz.cashguard.ml;

import com.fasterxml.jackson.databind.PropertyNamingStrategies;
import com.fasterxml.jackson.databind.annotation.JsonNaming;
import java.util.List;

@JsonNaming(PropertyNamingStrategies.SnakeCaseStrategy.class)
public record MlEvent(
        String typeId,
        String type,
        double timecodeSec,
        String description,
        List<MlEvidenceFrame> evidenceFrames,
        MlRule rule) {
}
