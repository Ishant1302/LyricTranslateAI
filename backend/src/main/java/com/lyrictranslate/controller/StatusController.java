package com.lyrictranslate.controller;

import com.lyrictranslate.JobsStore;
import com.lyrictranslate.model.Job;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.LinkedHashMap;
import java.util.Map;

/**
 * StatusController — GET /api/status/{jobId}
 *
 * Returns the current state of a processing job.
 * The frontend polls this every 1.5 seconds while processing.
 *
 * Direct Java equivalent of routes/sync.py::get_status()
 *
 * Response shape:
 * {
 *   "id":       "...",
 *   "status":   "processing" | "complete" | "error",
 *   "progress": 0–100,
 *   "step":     "Isolating Vocals",
 *   "error":    null | "...",
 *   "result":   null | { full lyric object }
 * }
 */
@RestController
@RequestMapping("/api")
public class StatusController {

    private final JobsStore store;

    public StatusController(JobsStore store) {
        this.store = store;
    }

    @GetMapping("/status/{jobId}")
    public ResponseEntity<Map<String, Object>> getStatus(@PathVariable String jobId) {
        Job job = store.getJob(jobId);
        if (job == null) {
            return ResponseEntity.status(404).body(
                Map.of("detail", "Job '" + jobId + "' not found.")
            );
        }

        // Only include result payload when complete (avoids sending large JSON on every poll)
        Map<String, Object> response = new LinkedHashMap<>();
        response.put("id",       job.id);
        response.put("status",   job.status);
        response.put("progress", job.progress);
        response.put("step",     job.step);
        response.put("error",    job.error);
        response.put("result",   "complete".equals(job.status) ? job.result : null);

        return ResponseEntity.ok(response);
    }

    /** Simple health-check — GET / */
    @GetMapping("/")
    public Map<String, Object> health() {
        return Map.of(
            "message", "LyricTranslate AI API is running 🎵",
            "version", "1.0.0"
        );
    }
}
