package kz.cashguard.job;

import java.nio.file.Path;
import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import org.springframework.stereotype.Component;

@Component
public class JobStore {

    private static final int ID_LENGTH = 8;

    private final Map<String, Job> jobs = new ConcurrentHashMap<>();
    private final Clock clock;

    public JobStore(Clock clock) {
        this.clock = clock;
    }

    public Job create(Path videoPath) {
        var job = new Job(newId(), videoPath, clock.instant());
        jobs.put(job.id(), job);
        return job;
    }

    public void remove(String jobId) {
        jobs.remove(jobId);
    }

    public Optional<Job> find(String jobId) {
        return Optional.ofNullable(jobs.get(jobId));
    }

    public List<Job> evictFinishedBefore(Duration ttl) {
        Instant cutoff = clock.instant().minus(ttl);
        List<Job> expired = jobs.values().stream()
                .filter(job -> job.finishedAt() != null && job.finishedAt().isBefore(cutoff))
                .toList();
        expired.forEach(job -> jobs.remove(job.id()));
        return expired;
    }

    private String newId() {
        return UUID.randomUUID().toString().replace("-", "").substring(0, ID_LENGTH);
    }
}
