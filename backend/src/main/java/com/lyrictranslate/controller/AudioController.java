package com.lyrictranslate.controller;

import com.lyrictranslate.JobsStore;
import com.lyrictranslate.model.Job;
import org.springframework.core.io.FileSystemResource;
import org.springframework.core.io.Resource;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.io.File;

/**
 * AudioController — GET /api/audio/{jobId}
 *
 * Streams the uploaded audio file back to the browser's AudioPlayer.
 * Equivalent of routes/sync.py::stream_audio() which uses FastAPI's FileResponse.
 *
 * Spring's FileSystemResource handles byte-range requests automatically,
 * so seeking in the AudioPlayer works correctly.
 */
@RestController
@RequestMapping("/api")
public class AudioController {

    private final JobsStore store;

    public AudioController(JobsStore store) {
        this.store = store;
    }

    @GetMapping("/audio/{jobId}")
    public ResponseEntity<Resource> streamAudio(@PathVariable String jobId) {
        Job job = store.getJob(jobId);
        if (job == null) {
            return ResponseEntity.status(404).build();
        }

        String filePath = job.filePath;
        if (filePath == null) {
            return ResponseEntity.status(404).build();
        }

        File audioFile = new File(filePath);
        if (!audioFile.exists()) {
            return ResponseEntity.status(404).build();
        }

        // Detect MIME type from extension
        String name = audioFile.getName().toLowerCase();
        MediaType mediaType;
        if      (name.endsWith(".mp3"))  mediaType = MediaType.parseMediaType("audio/mpeg");
        else if (name.endsWith(".wav"))  mediaType = MediaType.parseMediaType("audio/wav");
        else if (name.endsWith(".flac")) mediaType = MediaType.parseMediaType("audio/flac");
        else if (name.endsWith(".ogg"))  mediaType = MediaType.parseMediaType("audio/ogg");
        else if (name.endsWith(".m4a"))  mediaType = MediaType.parseMediaType("audio/mp4");
        else                             mediaType = MediaType.APPLICATION_OCTET_STREAM;

        Resource resource = new FileSystemResource(audioFile);

        return ResponseEntity.ok()
            .contentType(mediaType)
            .header(HttpHeaders.ACCEPT_RANGES, "bytes")
            .body(resource);
    }
}
