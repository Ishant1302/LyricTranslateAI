package com.lyrictranslate.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.stereotype.Service;

import java.io.IOException;
import java.net.*;
import java.net.http.*;
import java.time.Duration;
import java.util.*;
import java.util.logging.Logger;

/**
 * TranslationService — Lyric translation via Google's public HTTP API.
 *
 * Direct Java equivalent of services/claude_service.py.
 *
 * Strategy (identical to the Python version):
 *  1. Group segments into batches of BATCH_SIZE lines.
 *  2. Join with '\n', translate the whole block in one call.
 *  3. Split result back on '\n' — if the count matches, assign directly.
 *  4. If count mismatches, fall back to translating each segment individually.
 *  5. Exponential back-off on 429 / network errors.
 *
 * Uses Java 11+ HttpClient (no external dependency needed).
 */
@Service
public class TranslationService {

    private static final Logger log = Logger.getLogger(TranslationService.class.getName());

    private static final String GOOGLE_TRANSLATE_URL =
        "https://translate.googleapis.com/translate_a/single";

    private static final int BATCH_SIZE    = 50;
    private static final int MAX_RETRIES   = 3;
    private static final long BASE_DELAY_MS = 1000L;

    private static final ObjectMapper mapper = new ObjectMapper();
    private final HttpClient httpClient;

    public TranslationService() {
        this.httpClient = HttpClient.newBuilder()
            .connectTimeout(Duration.ofSeconds(20))
            .build();
    }

    // ── Low-level call ────────────────────────────────────────────────────

    /**
     * Single HTTP call to Google's public translate endpoint.
     * Equivalent of claude_service.py::_call_google()
     */
    private String callGoogle(String text, String source, String target) throws Exception {
        String query = "client=gtx&sl=" + URLEncoder.encode(source, "UTF-8")
            + "&tl=" + URLEncoder.encode(target, "UTF-8")
            + "&dt=t&q=" + URLEncoder.encode(text, "UTF-8");

        HttpRequest request = HttpRequest.newBuilder()
            .uri(URI.create(GOOGLE_TRANSLATE_URL + "?" + query))
            .header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
            .timeout(Duration.ofSeconds(20))
            .GET()
            .build();

        HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());

        if (response.statusCode() != 200) {
            throw new IOException("HTTP " + response.statusCode());
        }

        // Parse Google's response — format: [[["translated","original",...],...],...]
        List<?> data = mapper.readValue(response.body(), List.class);
        List<?> parts = (List<?>) data.get(0);
        StringBuilder sb = new StringBuilder();
        for (Object part : parts) {
            if (part instanceof List) {
                List<?> seg = (List<?>) part;
                if (!seg.isEmpty()) {
                    Object translated = seg.get(0);
                    if (translated != null) sb.append(translated);
                }
            }
        }
        return sb.toString().strip();
    }

    /**
     * Wrap callGoogle with exponential back-off on 429 / network errors.
     * Equivalent of claude_service.py::_call_with_backoff()
     */
    private String callWithBackoff(String text, String source, String target) throws Exception {
        long delay = BASE_DELAY_MS;
        Exception lastException = null;
        for (int attempt = 1; attempt <= MAX_RETRIES; attempt++) {
            try {
                return callGoogle(text, source, target);
            } catch (IOException exc) {
                lastException = exc;
                String msg = exc.getMessage();
                if (msg != null && msg.contains("429")) {
                    log.warning("Rate limited (429) — backing off " + delay + "ms (attempt " + attempt + "/" + MAX_RETRIES + ")");
                } else {
                    log.warning("Network error attempt " + attempt + "/" + MAX_RETRIES + ": " + exc.getMessage());
                }
                if (attempt < MAX_RETRIES) {
                    Thread.sleep(delay);
                    delay = Math.min(delay * 2, 30_000);
                }
            }
        }
        throw new RuntimeException("All retries exhausted", lastException);
    }

    // ── Batch translation ─────────────────────────────────────────────────

    /**
     * Translate a list of strings in a single API call.
     * Falls back to per-line translation on count mismatch.
     * Equivalent of claude_service.py::_translate_batch()
     */
    private List<String> translateBatch(List<String> lines, String source, String target) {
        if (lines.isEmpty()) return lines;

        String joined = String.join("\n", lines);
        try {
            String result = callWithBackoff(joined, source, target);
            String[] parts = result.split("\n", -1);
            if (parts.length == lines.size()) {
                return Arrays.asList(parts);
            }
            log.fine("Batch count mismatch (" + parts.length + " vs " + lines.size() + ") — falling back to per-line");
        } catch (Exception exc) {
            log.warning("Batch translate failed: " + exc.getMessage() + " — falling back to per-line");
        }

        // Per-line fallback
        List<String> results = new ArrayList<>();
        for (String line : lines) {
            if (line.isBlank()) {
                results.add(line);
                continue;
            }
            try {
                String translated = callWithBackoff(line, source, target);
                results.add(translated.isBlank() ? line : translated);
            } catch (Exception exc) {
                log.severe("Per-line translate failed: " + exc.getMessage());
                results.add(line);
            }
            try { Thread.sleep(50); } catch (InterruptedException ignored) {}
        }
        return results;
    }

    // ── Public API ────────────────────────────────────────────────────────

    /**
     * Translate all Whisper lyric segments to English.
     * Equivalent of claude_service.py::translate_segments()
     *
     * @param segments       List of segment maps (each must have a "text" key)
     * @param sourceLanguage ISO 639-1 code from Whisper ('es', 'ko', 'fr' …)
     * @return Segments with "translated" field added
     */
    @SuppressWarnings("unchecked")
    public List<Map<String, Object>> translateSegments(
        List<Map<String, Object>> segments,
        String sourceLanguage
    ) {
        if (segments == null || segments.isEmpty()) return segments;

        // Check if source is genuinely English (same logic as Python version)
        String allText = segments.stream()
            .map(s -> String.valueOf(s.getOrDefault("text", "")))
            .reduce("", (a, b) -> a + " " + b);
        boolean hasNonAscii = !allText.chars().allMatch(c -> c < 128);

        if (("en".equals(sourceLanguage) || "english".equals(sourceLanguage)) && !hasNonAscii) {
            log.info("Source is English (verified ASCII-only) — no translation needed");
            List<Map<String, Object>> result = new ArrayList<>();
            for (Map<String, Object> seg : segments) {
                Map<String, Object> copy = new HashMap<>(seg);
                copy.put("translated", seg.getOrDefault("text", ""));
                result.add(copy);
            }
            return result;
        }

        int total = segments.size();
        log.info(String.format("🌐 Translating %d segments in batches of %d: '%s' (auto-detect) → 'en'",
            total, BATCH_SIZE, sourceLanguage));

        List<String> texts           = new ArrayList<>();
        String[]     translatedTexts = new String[total];
        for (Map<String, Object> seg : segments) {
            texts.add(String.valueOf(seg.getOrDefault("text", "")).strip());
        }

        // Always use "auto" — safer than trusting Whisper's language detection on music
        String src        = "auto";
        int    numBatches = (total + BATCH_SIZE - 1) / BATCH_SIZE;

        for (int bIdx = 0; bIdx < numBatches; bIdx++) {
            int          start = bIdx * BATCH_SIZE;
            int          end   = Math.min(start + BATCH_SIZE, total);
            List<String> batch = texts.subList(start, end);

            List<String> results = translateBatch(batch, src, "en");
            for (int i = 0; i < results.size(); i++) {
                String t = results.get(i);
                translatedTexts[start + i] = (t != null && !t.isBlank()) ? t : texts.get(start + i);
            }

            // Brief pause between batches
            if (bIdx < numBatches - 1) {
                try { Thread.sleep(50); } catch (InterruptedException ignored) {}
            }
        }

        // Assemble result segments
        List<Map<String, Object>> resultSegments = new ArrayList<>();
        for (int i = 0; i < segments.size(); i++) {
            Map<String, Object> copy = new HashMap<>(segments.get(i));
            String translated = translatedTexts[i];
            copy.put("translated", translated != null ? translated : texts.get(i));
            resultSegments.add(copy);
        }

        log.info("✅ Translation done: " + total + " segments");
        return resultSegments;
    }
}
