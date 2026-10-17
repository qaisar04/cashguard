package kz.cashguard.api.dto;

import com.fasterxml.jackson.databind.PropertyNamingStrategies;
import com.fasterxml.jackson.databind.annotation.JsonNaming;
import java.util.List;

/** Exactly the fields of the case specification (section 10); the normative reference is part of the description. */
@JsonNaming(PropertyNamingStrategies.SnakeCaseStrategy.class)
public record ViolationDto(
        String type,
        double timecodeSec,
        String description,
        List<EvidenceFrameDto> evidenceFrames) {
}
