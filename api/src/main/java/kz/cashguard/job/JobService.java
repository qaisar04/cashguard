package kz.cashguard.job;

import java.nio.file.Path;
import java.time.Clock;
import java.util.List;
import java.util.concurrent.RejectedExecutionException;
import kz.cashguard.api.dto.EvidenceFrameDto;
import kz.cashguard.api.dto.JobResponse;
import kz.cashguard.api.dto.RuleReferenceDto;
import kz.cashguard.api.dto.Verdict;
import kz.cashguard.api.dto.ViolationDto;
import kz.cashguard.config.AppProperties;
import kz.cashguard.config.AsyncConfig;
import kz.cashguard.ml.MlClient;
import kz.cashguard.ml.MlEvent;
import kz.cashguard.ml.UnknownViolationTypeException;
import kz.cashguard.ml.ViolationType;
import kz.cashguard.storage.VideoStorage;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.core.task.TaskExecutor;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;
import org.springframework.web.multipart.MultipartFile;

@Service
public class JobService {

    private static final Logger log = LoggerFactory.getLogger(JobService.class);
    private static final long EVICTION_PERIOD_MS = 60_000;

    private final JobStore store;
    private final VideoStorage storage;
    private final MlClient mlClient;
    private final TaskExecutor executor;
    private final AppProperties properties;
    private final Clock clock;

    public JobService(JobStore store,
                      VideoStorage storage,
                      MlClient mlClient,
                      @Qualifier(AsyncConfig.JOB_EXECUTOR) TaskExecutor executor,
                      AppProperties properties,
                      Clock clock) {
        this.store = store;
        this.storage = storage;
        this.mlClient = mlClient;
        this.executor = executor;
        this.properties = properties;
        this.clock = clock;
    }

    public Job submit(MultipartFile file) {
        Path videoPath = storage.save(file);
        Job job = store.create(videoPath);
        try {
            executor.execute(() -> run(job));
        } catch (RejectedExecutionException e) {
            store.remove(job.id());
            storage.delete(videoPath);
            throw new JobQueueFullException();
        }
        return job;
    }

    public JobResponse status(String jobId) {
        Job job = store.find(jobId).orElseThrow(() -> new JobNotFoundException(jobId));
        return toResponse(job);
    }

    void run(Job job) {
        log.info("Job {} started: {}", job.id(), job.videoPath());
        try {
            List<ViolationDto> violations = mlClient.infer(job.videoPath()).stream().map(this::toViolation).toList();
            job.complete(violations, clock.instant());
            log.info("Job {} done: {} violation(s)", job.id(), violations.size());
        } catch (RuntimeException e) {
            job.fail(e.getMessage(), clock.instant());
            log.error("Job {} failed", job.id(), e);
        }
    }

    @Scheduled(fixedDelay = EVICTION_PERIOD_MS)
    void evictExpired() {
        store.evictFinishedBefore(properties.job().ttl()).forEach(job -> storage.delete(job.videoPath()));
    }

    private ViolationDto toViolation(MlEvent event) {
        ViolationType type = ViolationType.fromId(event.typeId())
                .orElseThrow(() -> new UnknownViolationTypeException(event.typeId()));
        List<EvidenceFrameDto> frames = event.evidenceFrames().stream()
                .map(frame -> new EvidenceFrameDto(frame.timestampSec(), frame.imageBase64()))
                .toList();
        RuleReferenceDto rule = event.rule() == null
                ? null
                : new RuleReferenceDto(event.rule().document(), event.rule().clause(), event.rule().url());
        return new ViolationDto(event.type(), type.id(), event.timecodeSec(), event.description(), frames, rule);
    }

    private static JobResponse toResponse(Job job) {
        return switch (job.status()) {
            case PROCESSING -> new JobResponse(job.id(), job.status().wire(), null, null, null);
            case DONE -> new JobResponse(job.id(), job.status().wire(),
                    Verdict.of(!job.violations().isEmpty()), job.violations(), null);
            case FAILED -> new JobResponse(job.id(), job.status().wire(), null, null, job.error());
        };
    }
}
