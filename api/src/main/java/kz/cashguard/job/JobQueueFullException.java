package kz.cashguard.job;

public class JobQueueFullException extends RuntimeException {

    public JobQueueFullException() {
        super("Processing queue is full, retry later");
    }
}
