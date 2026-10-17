package kz.cashguard.api;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.multipart;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import kz.cashguard.config.ApiKeyFilter;
import kz.cashguard.job.JobNotFoundException;
import kz.cashguard.job.JobService;
import kz.cashguard.storage.InvalidVideoException;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.context.annotation.Import;
import org.springframework.mock.web.MockMultipartFile;
import org.springframework.test.context.TestPropertySource;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;

@WebMvcTest({AnalyzeController.class, JobController.class})
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
class AnalyzeControllerTest {

    private static final String KEY = "test-key";

    @Autowired
    private MockMvc mvc;
    @MockitoBean
    private JobService jobService;

    @Test
    void rejectsWithoutApiKey() throws Exception {
        mvc.perform(multipart("/api/v1/analyze").file(video()))
                .andExpect(status().isUnauthorized());
    }

    @Test
    void returns400OnInvalidVideo() throws Exception {
        when(jobService.submit(any())).thenThrow(new InvalidVideoException("Unsupported file type"));

        mvc.perform(multipart("/api/v1/analyze").file(video()).header(ApiKeyFilter.HEADER, KEY))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.error").value("Unsupported file type"));
    }

    @Test
    void returns400WhenFilePartMissing() throws Exception {
        mvc.perform(multipart("/api/v1/analyze").header(ApiKeyFilter.HEADER, KEY))
                .andExpect(status().isBadRequest());
    }

    @Test
    void returns404ForUnknownJob() throws Exception {
        when(jobService.status("nope")).thenThrow(new JobNotFoundException("nope"));

        mvc.perform(get("/api/v1/jobs/nope").header(ApiKeyFilter.HEADER, KEY))
                .andExpect(status().isNotFound());
    }

    private static MockMultipartFile video() {
        return new MockMultipartFile("file", "v.mov", "video/quicktime", new byte[] {1});
    }
}
