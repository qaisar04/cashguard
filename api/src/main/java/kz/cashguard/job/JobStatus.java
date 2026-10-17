package kz.cashguard.job;

import com.fasterxml.jackson.annotation.JsonValue;

public enum JobStatus {
    PROCESSING("processing"),
    DONE("done"),
    FAILED("failed");

    private final String wire;

    JobStatus(String wire) {
        this.wire = wire;
    }

    @JsonValue
    public String wire() {
        return wire;
    }
}
