package kz.cashguard.api.dto;

import com.fasterxml.jackson.databind.PropertyNamingStrategies;
import com.fasterxml.jackson.databind.annotation.JsonNaming;
import java.util.List;

@JsonNaming(PropertyNamingStrategies.SnakeCaseStrategy.class)
public record ViolationDto(
        String type,
        String typeId,
        double timecodeSec,
        String description,
        List<EvidenceFrameDto> evidenceFrames,
        RuleReferenceDto rule) {
}
