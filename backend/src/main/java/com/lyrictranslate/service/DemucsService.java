package com.lyrictranslate.service;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.io.*;
import java.nio.file.*;
import java.util.*;
import java.util.logging.Logger;

/**
 * DemucsService — Vocal isolation via Facebook's Demucs model.
 *
 * Direct Java equivalent of services/demucs_service.py::isolate_vocals().
 * Runs Demucs as a Python subprocess via ProcessBuilder.
 *
 * ProcessBuilder replaces Python's subprocess.run().
 */
@Service
public class DemucsService {

    private static final Logger log = Logger.getLogger(DemucsService.class.getName());

    @Value("${app.demucs-model:htdemucs}")
    private String demucsModel;

    /**
     * Run Demucs vocal isolation on audioPath.
     *
     * @param audioPath  Absolute path to the input audio file
     * @param outputDir  Directory where Demucs will write its stems
     * @param progressCallback  Runnable called with estimated progress (not used in subprocess mode)
     * @return Path to the extracted vocals WAV file
     */
    public String isolateVocals(String audioPath, String outputDir) throws Exception {
        audioPath = Paths.get(audioPath).toAbsolutePath().toString();
        outputDir = Paths.get(outputDir).toAbsolutePath().toString();

        log.info("[Demucs] Starting vocal isolation for: " + audioPath);

        // Find Python executable — uses the same venv Python that has demucs installed
        String pythonExe = findPython();

        List<String> cmd = List.of(
            pythonExe, "-m", "demucs",
            "--two-stems", "vocals",
            "-n", demucsModel,
            "-o", outputDir,
            audioPath
        );

        log.info("[Demucs] Command: " + String.join(" ", cmd));

        ProcessBuilder pb = new ProcessBuilder(cmd);
        pb.redirectErrorStream(true);
        pb.directory(new File(System.getProperty("user.dir")));

        Process process = pb.start();
        String output = new String(process.getInputStream().readAllBytes());

        int exitCode = process.waitFor();
        if (exitCode != 0) {
            throw new RuntimeException("Demucs failed (exit " + exitCode + "):\n" + output);
        }

        log.info("[Demucs] Finished successfully");

        // Demucs writes to: outputDir/<model>/<stem_name>/vocals.wav
        String stemName  = Paths.get(audioPath).getFileName().toString()
                               .replaceAll("\\.[^.]+$", "");  // strip extension
        Path vocalsPath  = Paths.get(outputDir, demucsModel, stemName, "vocals.wav");

        if (!Files.exists(vocalsPath)) {
            // Fallback: search recursively for any vocals.wav
            Optional<Path> found = Files.walk(Paths.get(outputDir))
                .filter(p -> p.getFileName().toString().equals("vocals.wav"))
                .findFirst();
            if (found.isPresent()) {
                vocalsPath = found.get();
            } else {
                throw new RuntimeException(
                    "Demucs finished but vocals.wav not found under " + outputDir
                );
            }
        }

        log.info("[Demucs] Vocals isolated: " + vocalsPath);
        return vocalsPath.toString();
    }

    /**
     * Find the Python executable — prefers the venv Python inside backend/.
     * Falls back to system python3 / python.
     */
    public static String findPython() {
        // Check for venv alongside the backend directory
        String[] candidates = {
            "venv/Scripts/python.exe",    // Windows venv
            "venv/bin/python",            // Linux/Mac venv
            "python3",
            "python"
        };
        for (String candidate : candidates) {
            File f = new File(candidate);
            if (f.exists()) return f.getAbsolutePath();
        }
        return "python";  // last resort — relies on PATH
    }
}
