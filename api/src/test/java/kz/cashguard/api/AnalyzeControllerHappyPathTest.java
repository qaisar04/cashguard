package kz.cashguard.api;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.multipart;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import java.nio.file.Path;
import java.time.Clock;
import kz.cashguard.config.ApiKeyFilter;
import kz.cashguard.job.JobService;
import kz.cashguard.job.JobStore;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.context.annotation.Import;
import org.springframework.mock.web.MockMultipartFile;
import org.springframework.test.context.TestPropertySource;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;

@WebMvcTest(AnalyzeController.class)
@Import(kz.cashguard.config.SecurityConfig.class)
@TestPropertySource(properties = {
        "cashguard.api-key=test-key",
        "cashguard.ml.base-url=http://ml",
        "cashguard.ml.api-key=x",
        "cashguard.ml.timeout=1s",
        "cashguard.storage.dir=./target/videos",
        "cashguard.storage.max-upload=1MB",
        "cashguard.job.workers=1",
        "cashguard.job.queue-capacity=1",
        "cashguard.job.ttl=1h"})
class AnalyzeControllerHappyPathTest {

    @Autowired
    private MockMvc mvc;
    @MockitoBean
    private JobService jobService;

    @Test
    void returns202WithJobId() throws Exception {
        var job = new JobStore(Clock.systemUTC()).create(Path.of("v.mov"));
        when(jobService.submit(any())).thenReturn(job);

        mvc.perform(multipart("/api/v1/analyze")
                        .file(new MockMultipartFile("file", "v.mov", "video/quicktime", new byte[] {1}))
                        .header(ApiKeyFilter.HEADER, "test-key"))
                .andExpect(status().isAccepted())
                .andExpect(jsonPath("$.job_id").value(job.id()))
                .andExpect(jsonPath("$.status").value("processing"));
    }
}
