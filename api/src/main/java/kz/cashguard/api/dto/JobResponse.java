package kz.cashguard.api.dto;

import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.databind.PropertyNamingStrategies;
import com.fasterxml.jackson.databind.annotation.JsonNaming;
import java.util.List;

/** Public job payload; `verdict`/`violations` appear only when done, `error` only when failed. */
@JsonNaming(PropertyNamingStrategies.SnakeCaseStrategy.class)
@JsonInclude(JsonInclude.Include.NON_NULL)
public record JobResponse(
        String jobId,
        String status,
        Verdict verdict,
        List<ViolationDto> violations,
        String error) {
}
