"""
services/whisper_service.py — Speech-to-text using faster-whisper.

Speed-optimised single-pass strategy
--------------------------------------
We run Whisper ONCE with task="transcribe" to get original-language lyrics
with timestamps.  English translation is handled by claude_service.py using
Google Translate (batched, near-instant on text).

Key speed settings vs. the naive defaults:
  beam_size=2          — greedy-ish; ~2-3x faster than beam_size=5 with
                         negligible accuracy loss for music lyrics
  temperature=[0,0.4]  — try deterministic first, one fallback only
  vad_filter=False     — must stay off; Silero VAD silently drops music
                         sections it misclassifies as non-speech
  no_speech_threshold=0.80 — slightly more aggressive than 0.95 so genuinely
                         silent gaps are skipped faster

Hallucination prevention (same as before):
  condition_on_previous_text=False  — breaks the feedback/repetition loop
  compression_ratio_threshold=2.4  — rejects absurdly repetitive output
  _clean_segments()                 — sliding-window de-dup post-process
"""

import os
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)

_model = None
WHISPER_MODEL_SIZE = os.getenv("WHISPER_MODEL_SIZE", "base")


def _get_model():
    global _model
    if _model is None:
        from faster_whisper import WhisperModel
        logger.info(f"🤖 Loading Whisper model '{WHISPER_MODEL_SIZE}'...")
        _model = WhisperModel(WHISPER_MODEL_SIZE, device="cpu", compute_type="int8")
        logger.info("✅ Whisper model loaded")
    return _model


# ─── Hallucination cleaner ────────────────────────────────────────────────────

def _clean_segments(segments: List[Dict]) -> List[Dict]:
    """
    Post-processing to remove hallucination loops without discarding real lyrics.

    1. Consecutive-repeat filter: allow at most 2 back-to-back identical lines.
    2. Sliding-window density filter: within any 10-line window, same text
       may appear at most 3 times (choruses repeat; hallucinations appear 50x).
    """
    if not segments:
        return segments

    # Pass 1: consecutive repeat filter
    pass1, prev, run = [], None, 0
    for seg in segments:
        t = seg["text"].strip().lower()
        if t == prev:
            run += 1
            if run <= 2:
                pass1.append(seg)
        else:
            pass1.append(seg)
            run = 1
        prev = t

    # Pass 2: sliding-window density filter
    WINDOW, MAX_HITS = 10, 3
    pass2 = []
    for i, seg in enumerate(pass1):
        t = seg["text"].strip().lower()
        w_start = max(0, i - WINDOW)
        hits = sum(1 for s in pass1[w_start:i] if s["text"].strip().lower() == t)
        if hits < MAX_HITS:
            pass2.append(seg)

    removed = len(segments) - len(pass2)
    if removed > 0:
        logger.warning(f"🧹 Removed {removed} hallucinated segments")
    return pass2


# ─── Public API ───────────────────────────────────────────────────────────────

def transcribe_audio(audio_path: str, progress_callback=None) -> Dict:
    """
    Single-pass transcription in the source language.
    Translation to English is done separately by claude_service.translate_segments().

    Returns
    -------
    {
      "language":             str,
      "language_probability": float,
      "segments": [
        {"id", "start", "end", "duration", "text", "language"}, ...
      ]
    }
    """
    model = _get_model()
    logger.info(f"🎙️ Transcribing: {audio_path}")

    if progress_callback:
        progress_callback(2)

    segments_iter, info = model.transcribe(
        audio_path,
        task="transcribe",

        # ── Speed settings ────────────────────────────────────────────────
        beam_size=2,                          # was 5 — ~2-3x faster
        temperature=[0.0, 0.4],              # was 6 fallbacks — 2 is enough

        # ── Accuracy / hallucination prevention ───────────────────────────
        vad_filter=False,                    # must stay off for music
        condition_on_previous_text=False,    # prevents repetition loops
        compression_ratio_threshold=2.4,
        no_speech_threshold=0.80,            # was 0.95; skip genuine silence faster
        log_prob_threshold=-1.5,
    )

    language      = info.language
    language_prob = round(info.language_probability, 3)
    logger.info(f"Detected language: {language} ({language_prob:.1%})")

    if progress_callback:
        progress_callback(5)

    raw: List[Dict] = []
    segments_list = list(segments_iter)
    total = len(segments_list)

    for idx, seg in enumerate(segments_list):
        text = seg.text.strip()
        if not text:
            continue
        raw.append({
            "id":       idx,
            "start":    round(seg.start, 3),
            "end":      round(seg.end, 3),
            "duration": round(seg.end - seg.start, 3),
            "text":     text,
            "language": language,
        })
        if progress_callback and total > 0:
            progress_callback(int(5 + (idx / total) * 93))

    segments = _clean_segments(raw)

    if progress_callback:
        progress_callback(100)

    logger.info(
        f"✅ Transcription done: {len(segments)} segments kept "
        f"(raw={len(raw)}, removed={len(raw) - len(segments)})"
    )
    return {
        "language":             language,
        "language_probability": language_prob,
        "segments":             segments,
    }
