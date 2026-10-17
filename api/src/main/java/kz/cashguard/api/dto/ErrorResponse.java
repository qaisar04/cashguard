package kz.cashguard.api.dto;

import java.util.Map;

public record ErrorResponse(String error, Map<String, Object> details) {
}
