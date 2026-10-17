package kz.cashguard.config;

import java.util.concurrent.ThreadPoolExecutor;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.core.task.TaskExecutor;
import org.springframework.scheduling.concurrent.ThreadPoolTaskExecutor;

@Configuration
public class AsyncConfig {

    public static final String JOB_EXECUTOR = "jobExecutor";
    private static final String THREAD_PREFIX = "job-";

    @Bean(JOB_EXECUTOR)
    public TaskExecutor jobExecutor(AppProperties properties) {
        var executor = new ThreadPoolTaskExecutor();
        executor.setCorePoolSize(properties.job().workers());
        executor.setMaxPoolSize(properties.job().workers());
        executor.setQueueCapacity(properties.job().queueCapacity());
        executor.setThreadNamePrefix(THREAD_PREFIX);
        executor.setRejectedExecutionHandler(new ThreadPoolExecutor.AbortPolicy());
        executor.initialize();
        return executor;
    }
}
