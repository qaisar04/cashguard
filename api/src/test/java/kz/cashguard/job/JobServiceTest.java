package kz.cashguard.job;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import java.nio.file.Path;
import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.List;
import java.util.concurrent.RejectedExecutionException;
import kz.cashguard.api.dto.JobResponse;
import kz.cashguard.api.dto.Verdict;
import kz.cashguard.config.AppProperties;
import kz.cashguard.ml.MlClient;
import kz.cashguard.ml.MlEvent;
import kz.cashguard.ml.MlEvidenceFrame;
import kz.cashguard.ml.MlRule;
import kz.cashguard.ml.MlUnavailableException;
import kz.cashguard.storage.VideoStorage;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.core.task.SyncTaskExecutor;
import org.springframework.core.task.TaskExecutor;
import org.springframework.mock.web.MockMultipartFile;
import org.springframework.util.unit.DataSize;

@ExtendWith(MockitoExtension.class)
class JobServiceTest {

    private static final Path VIDEO = Path.of("/data/videos/test.mov");
    private static final String TYPE_ID = "workstation_unlocked";
    private static final String TYPE_RU = "Рабочая станция не заблокирована при уходе кассира";
    private static final double TIMECODE = 18.0;
    private static final Instant NOW = Instant.parse("2026-10-17T10:00:00Z");

    @Mock
    private VideoStorage storage;
    @Mock
    private MlClient mlClient;

    private JobService service;

    @BeforeEach
    void setUp() {
        Clock clock = Clock.fixed(NOW, ZoneOffset.UTC);
        service = new JobService(new JobStore(clock), storage, mlClient, new SyncTaskExecutor(), properties(), clock);
        when(storage.save(any())).thenReturn(VIDEO);
    }

    @Test
    void completesWithViolationVerdictWhenMlReturnsEvents() {
        var event = new MlEvent(TYPE_ID, TYPE_RU, TIMECODE, "desc",
                List.of(new MlEvidenceFrame(TIMECODE, "AAA=")), new MlRule("doc", "", "https://adilet.zan.kz"));
        when(mlClient.infer(VIDEO)).thenReturn(List.of(event));

        Job job = service.submit(file());
        JobResponse response = service.status(job.id());

        assertThat(response.status()).isEqualTo(JobStatus.DONE.wire());
        assertThat(response.verdict()).isEqualTo(Verdict.VIOLATION);
        assertThat(response.violations()).singleElement().satisfies(v -> {
            assertThat(v.type()).isEqualTo(TYPE_RU);
            assertThat(v.timecodeSec()).isEqualTo(TIMECODE);
            assertThat(v.evidenceFrames()).hasSize(1);
        });
    }

    @Test
    void completesWithNoViolationWhenMlReturnsNothing() {
        when(mlClient.infer(VIDEO)).thenReturn(List.of());

        Job job = service.submit(file());
        JobResponse response = service.status(job.id());

        assertThat(response.verdict()).isEqualTo(Verdict.NO_VIOLATION);
        assertThat(response.violations()).isEmpty();
    }

    @Test
    void failsWhenMlUnavailable() {
        when(mlClient.infer(VIDEO)).thenThrow(new MlUnavailableException("down", null));

        Job job = service.submit(file());
        JobResponse response = service.status(job.id());

        assertThat(response.status()).isEqualTo(JobStatus.FAILED.wire());
        assertThat(response.error()).isEqualTo("down");
        assertThat(response.verdict()).isNull();
    }

    @Test
    void failsOnUnknownViolationType() {
        var event = new MlEvent("made_up", "x", TIMECODE, "d", List.of(), null);
        when(mlClient.infer(VIDEO)).thenReturn(List.of(event));

        Job job = service.submit(file());

        assertThat(service.status(job.id()).status()).isEqualTo(JobStatus.FAILED.wire());
        assertThat(service.status(job.id()).error()).contains("made_up");
    }

    @Test
    void rejectsWhenQueueIsFull() {
        TaskExecutor rejecting = task -> {
            throw new RejectedExecutionException("full");
        };
        var clock = Clock.fixed(NOW, ZoneOffset.UTC);
        var store = new JobStore(clock);
        var full = new JobService(store, storage, mlClient, rejecting, properties(), clock);

        assertThatThrownBy(() -> full.submit(file())).isInstanceOf(JobQueueFullException.class);
        verify(storage).delete(VIDEO);
    }

    private static AppProperties properties() {
        return new AppProperties("k",
                new AppProperties.Ml("http://ml", "mk", Duration.ofSeconds(1)),
                new AppProperties.Storage("./data", DataSize.ofMegabytes(1)),
                new AppProperties.Job(1, 1, Duration.ofHours(1)));
    }

    private static MockMultipartFile file() {
        return new MockMultipartFile("file", "v.mov", "video/quicktime", new byte[] {1});
    }
}
