package kz.cashguard.job;

import java.nio.file.Path;
import java.time.Instant;
import java.util.List;
import kz.cashguard.api.dto.ViolationDto;

public final class Job {

    private final String id;
    private final Path videoPath;
    private final Instant createdAt;
    private volatile JobStatus status = JobStatus.PROCESSING;
    private volatile List<ViolationDto> violations = List.of();
    private volatile String error;
    private volatile Instant finishedAt;

    Job(String id, Path videoPath, Instant createdAt) {
        this.id = id;
        this.videoPath = videoPath;
        this.createdAt = createdAt;
    }

    public String id() {
        return id;
    }

    public Path videoPath() {
        return videoPath;
    }

    public Instant createdAt() {
        return createdAt;
    }

    public JobStatus status() {
        return status;
    }

    public List<ViolationDto> violations() {
        return violations;
    }

    public String error() {
        return error;
    }

    public Instant finishedAt() {
        return finishedAt;
    }

    void complete(List<ViolationDto> violations, Instant now) {
        this.violations = List.copyOf(violations);
        this.status = JobStatus.DONE;
        this.finishedAt = now;
    }

    void fail(String error, Instant now) {
        this.error = error;
        this.status = JobStatus.FAILED;
        this.finishedAt = now;
    }
}
