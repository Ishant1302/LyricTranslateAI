package com.lyrictranslate.controller;

import com.lyrictranslate.JobsStore;
import com.lyrictranslate.model.Job;
import com.lyrictranslate.service.PipelineService;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import java.util.logging.Logger;

/**
 * UploadController — POST /api/upload
 *
 * Accepts an audio file (multipart/form-data) or a song URL
 * and kicks off the async ML processing pipeline.
 *
 * Returns {job_id} immediately — frontend polls GET /api/status/{jobId}.
 *
 * Direct Java equivalent of routes/upload.py::upload_audio()
 */
@RestController
@RequestMapping("/api")
public class UploadController {

    private static final Logger log = Logger.getLogger(UploadController.class.getName());

    private static final Set<String> ALLOWED_EXTENSIONS = Set.of(
        ".mp3", ".wav", ".flac", ".ogg", ".m4a", ".aac"
    );

    private final JobsStore       store;
    private final PipelineService pipeline;

    @Value("${app.upload-dir:uploads}")
    private String uploadDir;

    public UploadController(JobsStore store, PipelineService pipeline) {
        this.store    = store;
        this.pipeline = pipeline;
    }

    @PostMapping("/upload")
    public ResponseEntity<Map<String, Object>> uploadAudio(
            @RequestParam(required = false) MultipartFile file,
            @RequestParam(required = false) String url,
            @RequestParam(required = false) String title,
            @RequestParam(required = false) String artist
    ) throws IOException {

        if (file == null && (url == null || url.isBlank())) {
            return ResponseEntity.badRequest().body(
                Map.of("detail", "Provide either an audio file or a URL.")
            );
        }

        String jobId  = UUID.randomUUID().toString();
        Path   jobDir = Paths.get(uploadDir, jobId);
        Files.createDirectories(jobDir);

        Map<String, Object> metadata = new HashMap<>();
        metadata.put("title",  title  != null && !title.isBlank()  ? title  : "Unknown Title");
        metadata.put("artist", artist != null && !artist.isBlank() ? artist : "Unknown Artist");

        store.createJob(jobId, metadata);
        store.updateProgress(jobId, 2, JobsStore.STEP_UPLOADING);

        if (file != null && !file.isEmpty()) {
            // ── File upload path ─────────────────────────────────────────────
            String originalName = file.getOriginalFilename() != null ? file.getOriginalFilename() : "audio";
            String ext = originalName.contains(".")
                ? originalName.substring(originalName.lastIndexOf('.')).toLowerCase()
                : ".mp3";

            if (!ALLOWED_EXTENSIONS.contains(ext)) {
                return ResponseEntity.status(HttpStatus.UNSUPPORTED_MEDIA_TYPE).body(
                    Map.of("detail", "Unsupported format '" + ext + "'. Allowed: " + ALLOWED_EXTENSIONS)
                );
            }

            Path audioPath = jobDir.resolve("original" + ext);
            file.transferTo(audioPath.toFile());

            store.updateFilePath(jobId, audioPath.toString());
            store.updateProgress(jobId, 8, JobsStore.STEP_UPLOADING);

            // Fire-and-forget async pipeline
            pipeline.runPipeline(jobId, audioPath.toString(), metadata);

        } else {
            // ── URL upload path ──────────────────────────────────────────────
            store.updateProgress(jobId, 2, "Queued — starting download…");
            // Download happens inside the async thread so we return immediately
            pipeline.runPipelineFromUrl(jobId, url, metadata);
        }

        Map<String, Object> response = new LinkedHashMap<>();
        response.put("job_id",  jobId);
        response.put("status",  "processing");
        response.put("message", "Pipeline started — poll /api/status/" + jobId + " for updates.");

        return ResponseEntity.status(HttpStatus.ACCEPTED).body(response);
    }
}
