package com.lyrictranslate.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.io.*;
import java.nio.file.*;
import java.util.*;
import java.util.logging.Logger;

/**
 * WhisperService — Speech-to-text transcription via faster-whisper.
 *
 * Direct Java equivalent of services/whisper_service.py::transcribe_audio().
 *
 * Since faster-whisper is a Python-only library, we delegate to a small
 * Python helper script (whisper_runner.py) via ProcessBuilder.
 * The script outputs clean JSON to stdout which we parse here.
 *
 * Output JSON shape (same as whisper_service.py):
 * {
 *   "language": "es",
 *   "language_probability": 0.98,
 *   "segments": [
 *     {"id": 0, "start": 0.0, "end": 3.2, "duration": 3.2, "text": "...", "language": "es"},
 *     ...
 *   ]
 * }
 */
@Service
public class WhisperService {

    private static final Logger log = Logger.getLogger(WhisperService.class.getName());
    private static final ObjectMapper mapper = new ObjectMapper();

    @Value("${app.whisper-model:base}")
    private String whisperModel;

    /**
     * Transcribe the audio file and return the full result map.
     *
     * @param audioPath  Absolute path to the audio file (WAV preferred)
     * @return Map with keys: language, language_probability, segments
     */
    @SuppressWarnings("unchecked")
    public Map<String, Object> transcribeAudio(String audioPath) throws Exception {
        log.info("🎙️ Transcribing: " + audioPath);

        String pythonExe   = DemucsService.findPython();
        String runnerScript = findWhisperRunner();

        List<String> cmd = List.of(pythonExe, runnerScript, audioPath);
        log.info("Whisper command: " + String.join(" ", cmd));

        ProcessBuilder pb = new ProcessBuilder(cmd);
        pb.environment().put("WHISPER_MODEL_SIZE", whisperModel);
        pb.directory(new File(System.getProperty("user.dir")));

        Process process = pb.start();

        // Capture stdout (JSON) and stderr (logs/warnings — don't fail on these)
        String stdout = new String(process.getInputStream().readAllBytes());
        String stderr = new String(process.getErrorStream().readAllBytes());

        int exitCode = process.waitFor();
        if (exitCode != 0) {
            throw new RuntimeException(
                "Whisper runner failed (exit " + exitCode + "):\n" + stderr
            );
        }

        if (stdout.isBlank()) {
            throw new RuntimeException("Whisper runner produced no output. Stderr:\n" + stderr);
        }

        // Parse the JSON output from whisper_runner.py
        Map<String, Object> result = mapper.readValue(stdout.trim(), Map.class);
        List<Map<String, Object>> segments = (List<Map<String, Object>>) result.get("segments");

        log.info(String.format(
            "✅ Transcription done: %d segments, language=%s",
            segments != null ? segments.size() : 0,
            result.get("language")
        ));
        return result;
    }

    /**
     * Locate whisper_runner.py — expected to be in the backend root directory.
     */
    private String findWhisperRunner() {
        // Look relative to the working directory (backend folder)
        Path runner = Paths.get("whisper_runner.py");
        if (Files.exists(runner)) return runner.toAbsolutePath().toString();

        // Also try next to the jar (when running packaged)
        Path nextToJar = Paths.get(System.getProperty("user.dir"), "whisper_runner.py");
        if (Files.exists(nextToJar)) return nextToJar.toString();

        throw new IllegalStateException(
            "whisper_runner.py not found. Expected at: " + runner.toAbsolutePath()
        );
    }
}
