package com.lyrictranslate;

import com.lyrictranslate.model.Job;
import org.springframework.stereotype.Component;

import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

/**
 * JobsStore — Thread-safe in-memory job registry.
 *
 * Direct Java equivalent of jobs_store.py.
 * Uses ConcurrentHashMap instead of Python's threading.RLock + dict.
 *
 * Spring singleton bean — injected wherever job state is needed.
 */
@Component
public class JobsStore {

    // Step label constants (mirrors jobs_store.py)
    public static final String STEP_UPLOADING    = "Uploading";
    public static final String STEP_ISOLATING    = "Isolating Vocals";
    public static final String STEP_TRANSCRIBING = "Transcribing";
    public static final String STEP_TRANSLATING  = "Translating";
    public static final String STEP_SYNCING      = "Syncing Lyrics";
    public static final String STEP_READY        = "Ready";

    private final ConcurrentHashMap<String, Job> jobs = new ConcurrentHashMap<>();

    // ── CRUD ────────────────────────────────────────────────────────────────

    /**
     * Initialise a new job entry with default values.
     * Equivalent of jobs_store.create_job().
     */
    public Job createJob(String jobId, Map<String, Object> metadata) {
        Job job = new Job(jobId, metadata);
        jobs.put(jobId, job);
        return job;
    }

    /**
     * Return the Job, or null if unknown.
     * Equivalent of jobs_store.get_job().
     */
    public Job getJob(String jobId) {
        return jobs.get(jobId);
    }

    /**
     * Update progress + step label.
     * Thread-safe: ConcurrentHashMap guarantees visibility across threads.
     */
    public void updateProgress(String jobId, int progress, String step) {
        Job job = jobs.get(jobId);
        if (job != null) {
            job.progress = progress;
            if (step != null) job.step = step;
        }
    }

    public void updateFilePath(String jobId, String filePath) {
        Job job = jobs.get(jobId);
        if (job != null) job.filePath = filePath;
    }

    public void updateVocalsPath(String jobId, String vocalsPath) {
        Job job = jobs.get(jobId);
        if (job != null) job.vocalsPath = vocalsPath;
    }

    public void updateMetadata(String jobId, Map<String, Object> metadata) {
        Job job = jobs.get(jobId);
        if (job != null) job.metadata = metadata;
    }

    public void updateSegments(String jobId, Object segments) {
        Job job = jobs.get(jobId);
        if (job != null) job.segments = segments;
    }

    /**
     * Mark a job as failed.
     * Equivalent of jobs_store.set_error().
     */
    public void setError(String jobId, String message) {
        Job job = jobs.get(jobId);
        if (job != null) {
            job.status = "error";
            job.error  = message;
        }
    }

    /**
     * Mark a job as complete with the final lyrics result.
     * Equivalent of jobs_store.set_complete().
     */
    public void setComplete(String jobId, Object result) {
        Job job = jobs.get(jobId);
        if (job != null) {
            job.status   = "complete";
            job.progress = 100;
            job.step     = STEP_READY;
            job.result   = result;
        }
    }
}
