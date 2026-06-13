"""
routes/upload.py — POST /api/upload

Accepts an audio file (MP3/WAV/FLAC/OGG) or a song URL and kicks off the
full asynchronous processing pipeline:

  Upload → Isolate Vocals → Transcribe → Translate → Sync → Done

Supported URL types:
  • YouTube  — direct download via yt-dlp
  • Spotify  — resolves track title/artist via Spotify's public oEmbed API,
               then searches YouTube for that track and downloads from there.
               No Spotify API key required!
  • SoundCloud, Bandcamp, etc. — handled directly by yt-dlp

The response returns immediately with a job_id so the frontend can start
polling GET /api/status/{job_id} for real-time progress updates.
"""

import os
import re
import uuid
import json
import hashlib
import asyncio
import logging
import aiofiles
from pathlib import Path
from typing import Optional

import requests as http_requests
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Request
from fastapi.responses import JSONResponse

import jobs_store as store
from services import demucs_service, whisper_service, claude_service

logger = logging.getLogger(__name__)
router = APIRouter()

# Directories
UPLOAD_DIR = Path("uploads")
CACHE_DIR  = Path("cache")
ALLOWED_EXTENSIONS = {".mp3", ".wav", ".flac", ".ogg", ".m4a", ".aac"}

# Speed optimisation: skip Demucs vocal isolation (raw audio → Whisper directly).
# This makes processing ~10x faster on CPU at slight accuracy cost.
SKIP_VOCAL_ISOLATION = os.getenv("SKIP_VOCAL_ISOLATION", "false").lower() == "true"


# ─── Helpers: caching ────────────────────────────────────────────────────────

def _md5_hash(path: str) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _check_cache(file_hash: str):
    cache_file = CACHE_DIR / file_hash / "result.json"
    if cache_file.exists():
        with open(cache_file, encoding="utf-8") as f:
            return json.load(f)
    return None


def _save_cache(file_hash: str, result: dict):
    cache_path = CACHE_DIR / file_hash
    cache_path.mkdir(parents=True, exist_ok=True)
    with open(cache_path / "result.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)


# ─── Helpers: Spotify URL handling ────────────────────────────────────────────

SPOTIFY_TRACK_RE = re.compile(
    r"https?://open\.spotify\.com/(?:intl-[a-z]+/)?track/([A-Za-z0-9]+)"
)

def _is_spotify_url(url: str) -> bool:
    return bool(SPOTIFY_TRACK_RE.search(url))


def _spotify_to_youtube_query(spotify_url: str) -> tuple[str, str, str]:
    """
    Given a Spotify track URL, return (youtube_search_query, title, artist)
    using Spotify's public oEmbed API — NO API key required.

    Example oEmbed response:
      {"title": "Yo Perreo Sola - Bad Bunny", "provider_name": "Spotify", ...}
    """
    # Use Spotify's public oEmbed endpoint (no auth needed)
    oembed_url = f"https://open.spotify.com/oembed?url={spotify_url}"
    try:
        resp = http_requests.get(oembed_url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        full_title = data.get("title", "")  # e.g. "Yo Perreo Sola - Bad Bunny"
        # Split "Song Title - Artist Name"
        if " - " in full_title:
            song_title, artist = full_title.split(" - ", 1)
        else:
            song_title = full_title
            artist = ""
        query = f"{song_title} {artist} official audio"
        return query, song_title.strip(), artist.strip()
    except Exception as e:
        logger.warning(f"Spotify oEmbed lookup failed: {e}")
        return "", "", ""


def _download_url(url: str, job_dir: Path) -> tuple[str, str, str]:
    """
    Download audio from a URL (YouTube, SoundCloud, Spotify, etc.)
    Returns (local_audio_path, song_title, artist_name)

    YouTube strategy
    ----------------
    Modern yt-dlp (2025+) requires a JavaScript runtime (deno/node) to solve
    YouTube's signature challenge when using the "web" player client.  The
    "android_vr" client bypasses this entirely — it authenticates differently
    and exposes audio-only streams (webm/m4a) without needing PO tokens or JS.

    After download we use imageio_ffmpeg to convert whatever format yt-dlp
    produced into a clean WAV file.  This is more reliable than the old
    approach of staging ffmpeg.exe as both ffmpeg AND ffprobe (ffprobe is a
    separate binary and the impostor caused postprocessor failures).
    """
    import yt_dlp
    import subprocess

    title_out = [""]
    artist_out = [""]
    spotify_title = ""
    spotify_artist = ""

    # ── Spotify: resolve via oEmbed → search YouTube ──────────────────────
    if _is_spotify_url(url):
        logger.info(f"Spotify URL detected — resolving via oEmbed: {url}")
        query, spotify_title, spotify_artist = _spotify_to_youtube_query(url)
        if not query:
            raise RuntimeError(
                "Could not resolve Spotify track info. "
                "Check that the URL is a public track (not a playlist or private)."
            )
        url = f"ytsearch1:{query}"
        logger.info(f"Searching YouTube for: {query}")

    # ── Download with bot-bypass strategy ────────────────────────────────
    # YouTube increasingly bot-detects yt-dlp. Priority order:
    #   1. cookies.txt file (most reliable — exported once via export_cookies.bat)
    #   2. android_vr / ios / web player clients (no auth)
    #   3. Live browser cookie extraction (chrome → edge → firefox)

    COOKIES_FILE = Path(__file__).parent.parent / "cookies.txt"

    def _build_ydl_opts(cookies_file=None, cookies_from_browser=None):
        opts = {
            "format": "bestaudio/best",
            "outtmpl": str(job_dir / "original.%(ext)s"),
            "extractor_args": {
                "youtube": {
                    "player_client": ["android_vr", "ios", "web"],
                }
            },
            "quiet": True,
            "no_warnings": False,
            "writethumbnail": False,
            "writeinfojson": False,
        }
        if cookies_file and Path(cookies_file).exists():
            opts["cookiefile"] = str(cookies_file)
            logger.info(f"Using cookies file: {cookies_file}")
        elif cookies_from_browser:
            opts["cookiesfrombrowser"] = (cookies_from_browser,)
        return opts

    def _try_download(opts):
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if "entries" in info:
                info = info["entries"][0]
            return info

    def _is_bot_error(exc):
        err = str(exc).lower()
        return any(k in err for k in ("sign in", "bot", "429", "cookies", "copy", "dpapi"))

    last_exc = None
    info = None

    # ── Attempt 1: cookies.txt file ───────────────────────────────────────
    if COOKIES_FILE.exists():
        try:
            opts = _build_ydl_opts(cookies_file=COOKIES_FILE)
            info = _try_download(opts)
            logger.info("YouTube download succeeded using cookies.txt")
        except Exception as exc:
            last_exc = exc
            if _is_bot_error(exc):
                logger.warning(f"cookies.txt attempt failed: {exc}")
            else:
                raise

    # ── Attempt 2: no cookies (android_vr client) ─────────────────────────
    if info is None:
        try:
            opts = _build_ydl_opts()
            info = _try_download(opts)
            logger.info("YouTube download succeeded without cookies")
        except Exception as exc:
            last_exc = exc
            if _is_bot_error(exc):
                logger.warning(f"No-cookie attempt failed: {exc}")
            else:
                raise

    # ── Attempt 3: live browser cookie extraction ─────────────────────────
    if info is None:
        for browser in ["chrome", "edge", "firefox"]:
            try:
                opts = _build_ydl_opts(cookies_from_browser=browser)
                info = _try_download(opts)
                logger.info(f"YouTube download succeeded using {browser} cookies")
                break
            except Exception as exc:
                last_exc = exc
                if _is_bot_error(exc):
                    logger.warning(f"Browser cookie attempt ({browser}) failed: {exc}")
                    continue
                raise

    if info is None:
        raise RuntimeError(
            "YouTube is blocking this download (bot detection). To fix this:\n"
            "1. Close all Chrome windows\n"
            "2. Run backend\\export_cookies.bat\n"
            "3. Try the YouTube link again.\n"
            f"(Last error: {last_exc})"
        )

    title_out[0]  = info.get("title", "")
    artist_out[0] = info.get("uploader", info.get("channel", ""))

    # Prefer Spotify metadata (more accurate) over YouTube metadata
    final_title  = spotify_title  or title_out[0]
    final_artist = spotify_artist or artist_out[0]

    # ── Find the downloaded file ──────────────────────────────────────────
    candidates = [p for p in job_dir.glob("original.*") if p.is_file()]
    if not candidates:
        raise RuntimeError("yt-dlp finished but no output file found.")
    downloaded_path = candidates[0]
    logger.info(f"Downloaded: {downloaded_path.name} ({downloaded_path.stat().st_size:,} bytes)")

    # ── Convert to WAV using imageio_ffmpeg ───────────────────────────────
    # Whisper handles WAV natively; imageio_ffmpeg ships its own binary so
    # we never depend on a system ffmpeg install.
    audio_path = str(downloaded_path)
    if downloaded_path.suffix.lower() not in {".wav"}:
        try:
            import imageio_ffmpeg
            ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
            wav_path = str(job_dir / "original.wav")
            result = subprocess.run(
                [ffmpeg_exe, "-y", "-i", str(downloaded_path),
                 "-ac", "1", "-ar", "16000", wav_path],
                capture_output=True,
                timeout=300,
            )
            if result.returncode == 0 and Path(wav_path).exists():
                logger.info(f"Converted to WAV: {wav_path}")
                audio_path = wav_path
            else:
                stderr_snippet = result.stderr.decode(errors="replace")[:300]
                logger.warning(f"WAV conversion failed (rc={result.returncode}): {stderr_snippet}")
                # Fall back to the raw downloaded file — Whisper may handle it
        except Exception as conv_err:
            logger.warning(f"imageio_ffmpeg conversion skipped: {conv_err}")

    return audio_path, final_title, final_artist


# ─── Full processing pipeline ─────────────────────────────────────────────────

def _build_waveform(audio_path: str, num_points: int = 200) -> list:
    try:
        import librosa
        import numpy as np

        y, _ = librosa.load(audio_path, sr=None, mono=True)
        chunk_size = max(1, len(y) // num_points)
        waveform = [
            float(np.max(np.abs(y[i: i + chunk_size])))
            for i in range(0, len(y) - chunk_size, chunk_size)
        ]
        max_val = max(waveform) if waveform else 1.0
        if max_val > 0:
            waveform = [round(v / max_val, 4) for v in waveform]
        return waveform[:num_points]
    except Exception as e:
        logger.warning(f"Waveform generation failed: {e}")
        return []


def _run_pipeline(job_id: str, audio_path: str, metadata: dict):
    """
    Full synchronous ML pipeline — runs in a thread pool executor.
    Updates the job store at each step so the frontend can poll progress.
    audio_path is already available on disk when this is called (file upload path).
    """
    _execute_pipeline(job_id, audio_path, metadata)


def _run_pipeline_from_url(job_id: str, url: str, metadata: dict):
    """
    URL variant: download audio first (inside the thread), then run the full pipeline.
    This avoids blocking FastAPI's async event loop during potentially long downloads.
    """
    job_dir = UPLOAD_DIR / job_id
    try:
        store.update_job(job_id, progress=3, step="Downloading audio from URL…")
        audio_path, ytitle, yartist = _download_url(url, job_dir)

        # Auto-fill metadata from URL if user left fields blank
        if metadata.get("title") == "Unknown Title" and ytitle:
            metadata["title"] = ytitle
        if metadata.get("artist") == "Unknown Artist" and yartist:
            metadata["artist"] = yartist

        store.update_job(job_id, file_path=audio_path, metadata=metadata, progress=8)
    except Exception as exc:
        logger.exception(f"Job {job_id} — download failed: {exc}")
        store.set_error(job_id, str(exc))
        return

    _execute_pipeline(job_id, audio_path, metadata)


def _execute_pipeline(job_id: str, audio_path: str, metadata: dict):
    """
    Core ML pipeline shared by both file and URL upload flows.
    """
    try:
        job_dir = UPLOAD_DIR / job_id

        # Step 0: hash + cache check
        store.update_job(job_id, progress=5, step="Checking cache")
        file_hash = _md5_hash(audio_path)
        cached = _check_cache(file_hash)
        if cached:
            logger.info(f"Cache hit for {file_hash}")
            store.set_complete(job_id, cached)
            return

        # Step 1: vocal isolation (Demucs) — or skip for speed
        if SKIP_VOCAL_ISOLATION:
            logger.info("[Fast mode] Skipping Demucs — using raw audio for transcription")
            store.update_job(job_id, progress=40, step="Skipping vocal isolation (fast mode)")
            vocals_path = audio_path  # pass raw audio straight to Whisper
        else:
            store.update_job(job_id, progress=10, step=store.STEP_ISOLATING)
            def demucs_cb(pct):
                store.update_job(job_id, progress=int(10 + pct * 0.30))

            vocals_dir  = str(job_dir / "demucs_out")
            vocals_path = demucs_service.isolate_vocals(audio_path, vocals_dir, progress_callback=demucs_cb)
            store.update_job(job_id, vocals_path=vocals_path, progress=40)

        # Step 2: transcription (Whisper)
        store.update_job(job_id, progress=42, step=store.STEP_TRANSCRIBING)
        def whisper_cb(pct):
            store.update_job(job_id, progress=int(42 + pct * 0.28))

        transcription = whisper_service.transcribe_audio(vocals_path, progress_callback=whisper_cb)
        segments = transcription["segments"]
        store.update_job(job_id, segments=segments, progress=70)

        # Step 3: translation (Claude)
        store.update_job(job_id, progress=72, step=store.STEP_TRANSLATING)
        def claude_cb(pct):
            store.update_job(job_id, progress=int(72 + pct * 0.18))

        translated_segments = claude_service.translate_segments(
            segments,
            source_language=transcription.get("language", "auto"),
            progress_callback=claude_cb,
        )
        store.update_job(job_id, progress=90)

        # Step 4: waveform + final result assembly
        store.update_job(job_id, progress=92, step=store.STEP_SYNCING)
        waveform = _build_waveform(audio_path)

        result = {
            "job_id":   job_id,
            "metadata": {
                **metadata,
                "language":             transcription.get("language"),
                "language_probability": transcription.get("language_probability"),
            },
            "waveform": waveform,
            "segments": [
                {
                    "id":         seg["id"],
                    "time":       seg["start"],
                    "duration":   seg["duration"],
                    "original":   seg["text"],
                    "translated": seg.get("translated", seg["text"]),
                    "language":   seg.get("language", ""),
                }
                for seg in translated_segments
            ],
        }

        _save_cache(file_hash, result)
        store.set_complete(job_id, result)
        logger.info(f"Job {job_id} complete — {len(result['segments'])} segments")

    except Exception as exc:
        logger.exception(f"Job {job_id} failed: {exc}")
        store.set_error(job_id, str(exc))


# ─── Upload endpoint ──────────────────────────────────────────────────────────

@router.post("/upload")
async def upload_audio(
    request: Request,
    file:   Optional[UploadFile] = File(None),
    url:    Optional[str]        = Form(None),
    title:  Optional[str]        = Form(None),
    artist: Optional[str]        = Form(None),
):
    """
    Accept an audio file or a URL (YouTube / Spotify / SoundCloud / etc.),
    persist it locally, and start the ML processing pipeline.

    Spotify links are automatically resolved:
      • Track info (title + artist) fetched from Spotify's public oEmbed API
      • Audio downloaded from the matching YouTube result via yt-dlp
      • No Spotify account or API key required!

    Returns {job_id} immediately — poll GET /api/status/{job_id} for progress.
    """
    if not file and not url:
        raise HTTPException(status_code=400, detail="Provide either an audio file or a URL.")

    job_id  = str(uuid.uuid4())
    job_dir = UPLOAD_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    metadata = {
        "title":  title or "Unknown Title",
        "artist": artist or "Unknown Artist",
    }

    store.create_job(job_id, metadata=metadata)
    store.update_job(job_id, progress=2, step=store.STEP_UPLOADING)

    # ── Save / download audio and launch pipeline ─────────────────────────
    executor = request.app.state.executor
    loop = asyncio.get_event_loop()

    if file:
        suffix = Path(file.filename).suffix.lower()
        if suffix not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=415,
                detail=f"Unsupported format '{suffix}'. Allowed: {', '.join(ALLOWED_EXTENSIONS)}",
            )
        audio_path = str(job_dir / f"original{suffix}")
        async with aiofiles.open(audio_path, "wb") as out:
            while chunk := await file.read(1024 * 1024):
                await out.write(chunk)

        store.update_job(job_id, file_path=audio_path, metadata=metadata, progress=8)
        # File is already on disk — launch the ML pipeline directly
        loop.run_in_executor(executor, _run_pipeline, job_id, audio_path, metadata)

    elif url:
        # Download happens inside the thread so we return job_id immediately
        # and the frontend polls for progress ("Downloading audio from URL…")
        store.update_job(job_id, progress=2, step="Queued — starting download…")
        loop.run_in_executor(executor, _run_pipeline_from_url, job_id, url, metadata)

    return JSONResponse(
        status_code=202,
        content={
            "job_id":  job_id,
            "status":  "processing",
            "message": "Pipeline started — poll /api/status/{job_id} for updates.",
        },
    )
