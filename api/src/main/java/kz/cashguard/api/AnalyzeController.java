package kz.cashguard.api;

import kz.cashguard.api.dto.AnalyzeResponse;
import kz.cashguard.job.Job;
import kz.cashguard.job.JobService;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestPart;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;

@RestController
@RequestMapping(ApiPaths.V1)
public class AnalyzeController {

    static final String FILE_PART = "file";

    private final JobService jobService;

    public AnalyzeController(JobService jobService) {
        this.jobService = jobService;
    }

    @PostMapping(value = ApiPaths.ANALYZE, consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    public ResponseEntity<AnalyzeResponse> analyze(@RequestPart(FILE_PART) MultipartFile file) {
        Job job = jobService.submit(file);
        return ResponseEntity.status(HttpStatus.ACCEPTED).body(new AnalyzeResponse(job.id(), job.status().wire()));
    }
}
