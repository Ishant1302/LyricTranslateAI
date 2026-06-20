package com.lyrictranslate.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.lyrictranslate.JobsStore;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Service;

import java.io.*;
import java.nio.file.*;
import java.security.MessageDigest;
import java.util.*;
import java.util.logging.Logger;

/**
 * PipelineService — Orchestrates the full ML pipeline in a background thread.
 *
 * Direct Java equivalent of the _run_pipeline() / _run_pipeline_from_url() /
 * _execute_pipeline() functions in routes/upload.py.
 *
 * @Async("pipelineExecutor") replaces loop.run_in_executor(executor, ...).
 * The method returns immediately; Spring runs it in the pipelineExecutor thread pool.
 *
 * Pipeline stages (same as Python):
 *   1. Hash check → cache lookup
 *   2. Demucs vocal isolation (or skip in fast mode)
 *   3. Whisper transcription
 *   4. Google Translate fallback for untranslated segments
 *   5. Waveform generation
 *   6. Assemble + cache result
 */
@Service
public class PipelineService {

    private static final Logger log = Logger.getLogger(PipelineService.class.getName());
    private static final ObjectMapper mapper = new ObjectMapper();

    private final JobsStore          store;
    private final DemucsService      demucs;
    private final WhisperService     whisper;
    private final TranslationService translator;
    private final YtDlpService       ytDlp;

    @Value("${app.upload-dir:uploads}")
    private String uploadDir;

    @Value("${app.cache-dir:cache}")
    private String cacheDir;

    @Value("${app.skip-vocal-isolation:false}")
    private boolean skipVocalIsolation;

    public PipelineService(
        JobsStore store,
        DemucsService demucs,
        WhisperService whisper,
        TranslationService translator,
        YtDlpService ytDlp
    ) {
        this.store      = store;
        this.demucs     = demucs;
        this.whisper    = whisper;
        this.translator = translator;
        this.ytDlp      = ytDlp;
    }

    // ── Public entry points (called from UploadController) ──────────────────

    /**
     * File upload path: audio is already on disk, run pipeline directly.
     * Equivalent of _run_pipeline() in upload.py.
     */
    @Async("pipelineExecutor")
    public void runPipeline(String jobId, String audioPath, Map<String, Object> metadata) {
        executePipeline(jobId, audioPath, metadata);
    }

    /**
     * URL upload path: download audio first (inside thread), then run pipeline.
     * Equivalent of _run_pipeline_from_url() in upload.py.
     */
    @Async("pipelineExecutor")
    public void runPipelineFromUrl(String jobId, String url, Map<String, Object> metadata) {
        Path jobDir = Paths.get(uploadDir, jobId);
        try {
            store.updateProgress(jobId, 3, "Downloading audio from URL…");
            String[] downloaded = ytDlp.downloadUrl(url, jobDir);
            String audioPath    = downloaded[0];
            String ytTitle      = downloaded[1];
            String ytArtist     = downloaded[2];

            // Auto-fill metadata from URL if user left fields blank
            Map<String, Object> meta = new HashMap<>(metadata);
            if ("Unknown Title".equals(meta.get("title")) && !ytTitle.isBlank()) {
                meta.put("title", ytTitle);
            }
            if ("Unknown Artist".equals(meta.get("artist")) && !ytArtist.isBlank()) {
                meta.put("artist", ytArtist);
            }
            store.updateFilePath(jobId, audioPath);
            store.updateMetadata(jobId, meta);
            store.updateProgress(jobId, 8, JobsStore.STEP_UPLOADING);

            executePipeline(jobId, audioPath, meta);

        } catch (Exception exc) {
            log.severe("Job " + jobId + " — download failed: " + exc.getMessage());
            store.setError(jobId, exc.getMessage());
        }
    }

    // ── Core pipeline ────────────────────────────────────────────────────────

    /**
     * Equivalent of _execute_pipeline() in upload.py.
     */
    @SuppressWarnings("unchecked")
    private void executePipeline(String jobId, String audioPath, Map<String, Object> metadata) {
        try {
            Path jobDir = Paths.get(uploadDir, jobId);

            // Step 0: hash + cache check
            store.updateProgress(jobId, 5, "Checking cache");
            String fileHash = md5Hash(audioPath);
            Map<String, Object> cached = checkCache(fileHash);
            if (cached != null) {
                log.info("Cache hit for " + fileHash);
                store.setComplete(jobId, cached);
                return;
            }

            // Step 1: vocal isolation (Demucs) — or skip for speed
            String vocalsPath;
            if (skipVocalIsolation) {
                log.info("[Fast mode] Skipping Demucs — using raw audio for transcription");
                store.updateProgress(jobId, 40, "Skipping vocal isolation (fast mode)");
                vocalsPath = audioPath;
            } else {
                store.updateProgress(jobId, 10, JobsStore.STEP_ISOLATING);
                String vocalsDir = jobDir.resolve("demucs_out").toString();
                vocalsPath = demucs.isolateVocals(audioPath, vocalsDir);
                store.updateVocalsPath(jobId, vocalsPath);
                store.updateProgress(jobId, 40, JobsStore.STEP_ISOLATING);
            }

            // Step 2: Whisper transcription
            store.updateProgress(jobId, 42, JobsStore.STEP_TRANSCRIBING);
            Map<String, Object> transcription = whisper.transcribeAudio(vocalsPath);
            List<Map<String, Object>> segments =
                (List<Map<String, Object>>) transcription.get("segments");
            store.updateSegments(jobId, segments);
            store.updateProgress(jobId, 80, JobsStore.STEP_TRANSCRIBING);

            // Step 3: Google Translate fallback for un-translated segments
            List<Map<String, Object>> untranslated = new ArrayList<>();
            for (Map<String, Object> seg : segments) {
                if (seg.get("translated") == null) untranslated.add(seg);
            }

            if (!untranslated.isEmpty()) {
                log.info("Running Google Translate fallback for " + untranslated.size() + " segments");
                store.updateProgress(jobId, 82, JobsStore.STEP_TRANSLATING);

                List<Map<String, Object>> filled = translator.translateSegments(
                    untranslated,
                    String.valueOf(transcription.getOrDefault("language", "auto"))
                );

                // Merge translations back by segment id
                Map<Object, String> filledMap = new HashMap<>();
                for (Map<String, Object> s : filled) {
                    Object tval = s.get("translated");
                    if (tval == null) tval = s.get("text");
                    filledMap.put(s.get("id"), tval != null ? tval.toString() : "");
                }
                for (Map<String, Object> seg : segments) {
                    if (seg.get("translated") == null) {
                        String t = filledMap.get(seg.get("id"));
                        seg.put("translated", t != null ? t : seg.get("text"));
                    }
                }
            } else {
                log.info("All segments translated by Whisper — skipping Google Translate");
            }

            store.updateProgress(jobId, 90, null);

            // Step 4: waveform + final result assembly
            store.updateProgress(jobId, 92, JobsStore.STEP_SYNCING);
            List<Double> waveform = buildWaveform(audioPath, 200);

            // Build final result segments
            List<Map<String, Object>> resultSegments = new ArrayList<>();
            for (Map<String, Object> seg : segments) {
                Map<String, Object> out = new LinkedHashMap<>();
                out.put("id",         seg.get("id"));
                out.put("time",       seg.get("start"));
                out.put("duration",   seg.get("duration"));
                out.put("original",   seg.get("text"));
                out.put("translated", seg.getOrDefault("translated", seg.get("text")));
                out.put("language",   seg.getOrDefault("language", ""));
                resultSegments.add(out);
            }

            // Build metadata with language info
            Map<String, Object> finalMeta = new HashMap<>(metadata);
            finalMeta.put("language",             transcription.get("language"));
            finalMeta.put("language_probability", transcription.get("language_probability"));

            Map<String, Object> result = new LinkedHashMap<>();
            result.put("job_id",   jobId);
            result.put("metadata", finalMeta);
            result.put("waveform", waveform);
            result.put("segments", resultSegments);

            saveCache(fileHash, result);
            store.setComplete(jobId, result);
            log.info("Job " + jobId + " complete — " + resultSegments.size() + " segments");

        } catch (Exception exc) {
            log.severe("Job " + jobId + " failed: " + exc.getMessage());
            store.setError(jobId, exc.getMessage());
        }
    }

    // ── Helpers ──────────────────────────────────────────────────────────────

    /**
     * Compute MD5 hash of a file.
     * Equivalent of _md5_hash() in upload.py.
     */
    private String md5Hash(String filePath) throws Exception {
        MessageDigest md = MessageDigest.getInstance("MD5");
        try (InputStream is = new BufferedInputStream(new FileInputStream(filePath))) {
            byte[] buf = new byte[65536];
            int n;
            while ((n = is.read(buf)) != -1) md.update(buf, 0, n);
        }
        byte[] digest = md.digest();
        StringBuilder sb = new StringBuilder();
        for (byte b : digest) sb.append(String.format("%02x", b));
        return sb.toString();
    }

    /**
     * Check if a cached result exists for this file hash.
     * Equivalent of _check_cache() in upload.py.
     */
    @SuppressWarnings("unchecked")
    private Map<String, Object> checkCache(String fileHash) {
        Path cacheFile = Paths.get(cacheDir, fileHash, "result.json");
        if (Files.exists(cacheFile)) {
            try {
                return mapper.readValue(cacheFile.toFile(), Map.class);
            } catch (Exception e) {
                log.warning("Failed to read cache: " + e.getMessage());
            }
        }
        return null;
    }

    /**
     * Save result to cache.
     * Equivalent of _save_cache() in upload.py.
     */
    private void saveCache(String fileHash, Map<String, Object> result) {
        try {
            Path cachePath = Paths.get(cacheDir, fileHash);
            Files.createDirectories(cachePath);
            mapper.writerWithDefaultPrettyPrinter()
                  .writeValue(cachePath.resolve("result.json").toFile(), result);
        } catch (Exception e) {
            log.warning("Failed to save cache: " + e.getMessage());
        }
    }

    /**
     * Build a simple waveform from an audio file by sampling amplitude.
     * Uses WAV raw PCM data for WAV files; returns empty list for other formats.
     * Equivalent of _build_waveform() in upload.py (which used librosa).
     */
    private List<Double> buildWaveform(String audioPath, int numPoints) {
        try {
            if (!audioPath.toLowerCase().endsWith(".wav")) {
                // For non-WAV files generate a placeholder sine-like waveform
                List<Double> wf = new ArrayList<>();
                for (int i = 0; i < numPoints; i++) {
                    wf.add(Math.round(Math.abs(Math.sin(i * 0.15)) * 10000.0) / 10000.0);
                }
                return wf;
            }

            // Read WAV PCM data and sample amplitude
            try (RandomAccessFile raf = new RandomAccessFile(audioPath, "r")) {
                // Skip 44-byte WAV header
                raf.seek(44);
                long dataLen = raf.length() - 44;
                long chunkSize = Math.max(1, dataLen / (numPoints * 2L));

                List<Double> waveform = new ArrayList<>();
                for (int i = 0; i < numPoints; i++) {
                    long pos = 44 + i * chunkSize * 2;
                    if (pos >= raf.length()) break;
                    raf.seek(pos);
                    int maxAbs = 0;
                    for (int j = 0; j < chunkSize && raf.getFilePointer() + 2 <= raf.length(); j++) {
                        int sample = raf.readShort();
                        maxAbs = Math.max(maxAbs, Math.abs(sample));
                    }
                    waveform.add(maxAbs / 32768.0);
                }

                // Normalize
                double max = waveform.stream().mapToDouble(Double::doubleValue).max().orElse(1.0);
                if (max > 0) {
                    waveform.replaceAll(v -> Math.round(v / max * 10000.0) / 10000.0);
                }
                return waveform;
            }
        } catch (Exception e) {
            log.warning("Waveform generation failed: " + e.getMessage());
            return Collections.emptyList();
        }
    }
}
