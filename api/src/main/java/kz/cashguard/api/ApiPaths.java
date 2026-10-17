package kz.cashguard.api;

public final class ApiPaths {

    public static final String V1 = "/api/v1";
    public static final String ANALYZE = "/analyze";
    public static final String JOBS = "/jobs";
    public static final String JOB_BY_ID = JOBS + "/{jobId}";

    private ApiPaths() {
    }
}
