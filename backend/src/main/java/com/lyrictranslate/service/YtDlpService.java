package com.lyrictranslate.service;

import org.springframework.stereotype.Service;

import java.io.*;
import java.nio.file.*;
import java.util.*;
import java.util.logging.Logger;
import java.util.regex.*;

/**
 * YtDlpService — Download audio from YouTube, SoundCloud, Spotify etc.
 *
 * Direct Java equivalent of the _download_url() + _spotify_to_youtube_query()
 * functions in routes/upload.py.
 *
 * yt-dlp is a Python CLI tool — we invoke it via ProcessBuilder.
 * Spotify URLs are first resolved via the public oEmbed API, then
 * searched on YouTube (no API key needed — identical to Python version).
 */
@Service
public class YtDlpService {

    private static final Logger log = Logger.getLogger(YtDlpService.class.getName());

    private static final Pattern SPOTIFY_TRACK_RE = Pattern.compile(
        "https?://open\\.spotify\\.com/(?:intl-[a-z]+/)?track/([A-Za-z0-9]+)"
    );

    /**
     * Download audio from a URL.
     * @return String[3] — {localAudioPath, songTitle, artistName}
     */
    public String[] downloadUrl(String url, Path jobDir) throws Exception {
        String[] titleArtist = {"", ""};

        // ── Spotify: resolve to YouTube search ──────────────────────────────
        if (isSpotifyUrl(url)) {
            log.info("Spotify URL detected — resolving via oEmbed: " + url);
            String[] spotifyMeta = spotifyToYoutubeQuery(url);
            String query = spotifyMeta[0];
            if (query.isBlank()) {
                throw new RuntimeException(
                    "Could not resolve Spotify track info. " +
                    "Check that the URL is a public track (not a playlist or private)."
                );
            }
            titleArtist[0] = spotifyMeta[1];
            titleArtist[1] = spotifyMeta[2];
            url = "ytsearch1:" + query;
            log.info("Searching YouTube for: " + query);
        }

        String ytdlpExe  = findYtDlp();
        String outputTpl = jobDir.resolve("original.%(ext)s").toString();

        // Try multiple strategies (mirrors Python's 3-attempt logic)
        Path cookiesFile = Paths.get("cookies.txt");
        String[] strategies = cookiesFile.toFile().exists()
            ? new String[]{"cookies", "no-cookies"}
            : new String[]{"no-cookies"};

        Exception lastException = null;
        for (String strategy : strategies) {
            try {
                List<String> cmd = new ArrayList<>(List.of(
                    ytdlpExe,
                    "--format", "bestaudio/best",
                    "--output", outputTpl,
                    "--extractor-args", "youtube:player_client=android_vr,ios,web",
                    "--no-playlist",
                    "--quiet",
                    "--print", "%(title)s|||%(uploader)s"
                ));
                if ("cookies".equals(strategy)) {
                    cmd.addAll(List.of("--cookies", cookiesFile.toAbsolutePath().toString()));
                }
                cmd.add(url);

                ProcessBuilder pb = new ProcessBuilder(cmd);
                pb.directory(new File(System.getProperty("user.dir")));
                Process proc = pb.start();

                String stdout = new String(proc.getInputStream().readAllBytes());
                String stderr = new String(proc.getErrorStream().readAllBytes());
                int exitCode  = proc.waitFor();

                if (exitCode != 0) {
                    boolean isBot = stderr.toLowerCase().contains("sign in")
                        || stderr.toLowerCase().contains("bot")
                        || stderr.toLowerCase().contains("429");
                    if (isBot) {
                        log.warning("Bot detection with strategy '" + strategy + "': " + stderr.substring(0, Math.min(200, stderr.length())));
                        lastException = new RuntimeException(stderr);
                        continue;
                    }
                    throw new RuntimeException("yt-dlp failed (exit " + exitCode + "):\n" + stderr);
                }

                // Parse title|||uploader from stdout
                String line = stdout.lines().findFirst().orElse("").strip();
                if (line.contains("|||")) {
                    String[] parts = line.split("\\|\\|\\|", 2);
                    if (titleArtist[0].isBlank()) titleArtist[0] = parts[0].strip();
                    if (titleArtist[1].isBlank() && parts.length > 1) titleArtist[1] = parts[1].strip();
                }

                // Find downloaded file
                Optional<Path> downloaded = Files.list(jobDir)
                    .filter(p -> p.getFileName().toString().startsWith("original.") && Files.isRegularFile(p))
                    .findFirst();

                if (downloaded.isEmpty()) {
                    throw new RuntimeException("yt-dlp finished but no output file found.");
                }

                log.info("Downloaded: " + downloaded.get().getFileName() +
                    " (" + Files.size(downloaded.get()) + " bytes)");

                return new String[]{downloaded.get().toString(), titleArtist[0], titleArtist[1]};

            } catch (RuntimeException e) {
                lastException = e;
                if (e.getMessage() != null && (
                    e.getMessage().contains("sign in") ||
                    e.getMessage().contains("bot") ||
                    e.getMessage().contains("429"))) {
                    continue;
                }
                throw e;
            }
        }

        throw new RuntimeException(
            "YouTube is blocking this download (bot detection). To fix this:\n" +
            "1. Close all Chrome windows\n" +
            "2. Run backend\\export_cookies.bat\n" +
            "3. Try the YouTube link again.\n" +
            "(Last error: " + lastException + ")"
        );
    }

    /**
     * Resolve a Spotify track URL to a YouTube search query using oEmbed.
     * No API key required — same approach as Python version.
     * @return String[3] — {youtubeSearchQuery, songTitle, artistName}
     */
    private String[] spotifyToYoutubeQuery(String spotifyUrl) {
        String oembedUrl = "https://open.spotify.com/oembed?url=" + spotifyUrl;
        try {
            java.net.http.HttpClient client = java.net.http.HttpClient.newHttpClient();
            java.net.http.HttpRequest req = java.net.http.HttpRequest.newBuilder()
                .uri(java.net.URI.create(oembedUrl))
                .timeout(java.time.Duration.ofSeconds(10))
                .GET()
                .build();
            java.net.http.HttpResponse<String> resp =
                client.send(req, java.net.http.HttpResponse.BodyHandlers.ofString());

            com.fasterxml.jackson.databind.ObjectMapper m = new com.fasterxml.jackson.databind.ObjectMapper();
            @SuppressWarnings("unchecked")
            Map<String, Object> data = m.readValue(resp.body(), Map.class);
            String fullTitle = String.valueOf(data.getOrDefault("title", ""));

            String songTitle = fullTitle, artist = "";
            if (fullTitle.contains(" - ")) {
                String[] parts = fullTitle.split(" - ", 2);
                songTitle = parts[0].strip();
                artist    = parts[1].strip();
            }
            String query = songTitle + " " + artist + " official audio";
            return new String[]{query, songTitle, artist};

        } catch (Exception e) {
            log.warning("Spotify oEmbed lookup failed: " + e.getMessage());
            return new String[]{"", "", ""};
        }
    }

    private boolean isSpotifyUrl(String url) {
        return SPOTIFY_TRACK_RE.matcher(url).find();
    }

    private String findYtDlp() {
        for (String candidate : new String[]{"yt-dlp", "yt-dlp.exe"}) {
            try {
                Process p = new ProcessBuilder(candidate, "--version").start();
                if (p.waitFor() == 0) return candidate;
            } catch (Exception ignored) {}
        }
        return "yt-dlp";  // rely on PATH
    }
}
