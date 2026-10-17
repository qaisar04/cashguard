package kz.cashguard.api;

import kz.cashguard.api.dto.JobResponse;
import kz.cashguard.job.JobService;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping(ApiPaths.V1)
public class JobController {

    private final JobService jobService;

    public JobController(JobService jobService) {
        this.jobService = jobService;
    }

    @GetMapping(ApiPaths.JOB_BY_ID)
    public ResponseEntity<JobResponse> status(@PathVariable String jobId) {
        return ResponseEntity.ok(jobService.status(jobId));
    }
}
