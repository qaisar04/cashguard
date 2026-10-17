package kz.cashguard.api.dto;

import com.fasterxml.jackson.annotation.JsonValue;

public enum Verdict {
    VIOLATION("violation"),
    NO_VIOLATION("no_violation");

    private final String wire;

    Verdict(String wire) {
        this.wire = wire;
    }

    @JsonValue
    public String wire() {
        return wire;
    }

    public static Verdict of(boolean hasViolations) {
        return hasViolations ? VIOLATION : NO_VIOLATION;
    }
}
