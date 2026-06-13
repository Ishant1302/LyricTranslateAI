"""
services/whisper_service.py — Speech-to-text using faster-whisper.

Root problem diagnosis:
  • vad_filter=True on raw mixed audio (music + vocals) silently DROPS most of the
    song because Silero VAD classifies background music as "not speech".
    Result: only 9-10 lines from a 4:40 song.
  • vad_filter=False + temperature=0 + condition_on_previous_text=True → loops.

Solution:
  • Disable VAD entirely (vad_filter=False) → nothing is ever silently skipped.
  • Break feedback loop: condition_on_previous_text=False → model can't repeat itself.
  • Temperature fallback [0..1] → if greedy decoding creates repetitive output,
    auto-retry with increasing randomness until compression check passes.
  • compression_ratio_threshold=2.4 → only reject genuinely absurd repetitions.
  • Strong post-processing: sliding window deduplication that catches any leftover
    hallucination loops that slipped through model-level filters.
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


def _clean_segments(segments: List[Dict]) -> List[Dict]:
    """
    Post-processing to remove hallucination loops without discarding real lyrics.

    Strategy
    --------
    1. Consecutive-repeat filter: allow at most 2 back-to-back identical lines
       (some songs do say "oh-oh" twice), drop any 3rd+ consecutive repeat.
    2. Sliding-window density filter: within any 10-line window, if the same
       normalised text appears more than 3 times, drop the extras.
       Real chorus lines can appear 2-3 times in a song; hallucinations appear
       10-50 times across the window.
    """
    if not segments:
        return segments

    # Pass 1: consecutive repeat filter (≥3 in a row = hallucination)
    pass1 = []
    prev, run = None, 0
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

    # Pass 2: sliding-window density filter (window = 10 segments)
    WINDOW, MAX_WITHIN_WINDOW = 10, 3
    pass2 = []
    for i, seg in enumerate(pass1):
        t = seg["text"].strip().lower()
        window_start = max(0, i - WINDOW)
        count_in_window = sum(
            1 for s in pass1[window_start:i]
            if s["text"].strip().lower() == t
        )
        if count_in_window < MAX_WITHIN_WINDOW:
            pass2.append(seg)

    removed = len(segments) - len(pass2)
    if removed > 0:
        logger.warning(f"🧹 Removed {removed} hallucinated segments")

    return pass2


def transcribe_audio(audio_path: str, progress_callback=None) -> Dict:
    """
    Transcribe the full audio file and return timestamped lyric segments.

    Why vad_filter=False?
    ---------------------
    Silero VAD (used by faster-whisper) is trained on clean speech recordings.
    When applied to music, it classifies large sections of background music as
    "non-speech" and silently skips them — resulting in only 9-10 lines from a
    4+ minute song. Disabling VAD ensures the ENTIRE file is processed.

    Hallucination prevention (replaces VAD):
    - condition_on_previous_text=False  → breaks the feedback loop that causes
      "same phrase repeated 100 times" — the single most effective setting.
    - temperature=[0.0..1.0]            → auto-retries with randomness when the
      greedy decode is detected as repetitive (compression ratio too high).
    - compression_ratio_threshold=2.4  → rejects segments with absurdly repeated
      text (real lyrics score < 2.0, hallucinations often score > 3.0+).
    - _clean_segments()                 → post-processing safety net.
    """
    model = _get_model()
    logger.info(f"🎙️ Transcribing (full file, no VAD skip): {audio_path}")

    if progress_callback:
        progress_callback(2)

    segments_iter, info = model.transcribe(
        audio_path,
        beam_size=5,

        # ── No VAD — process the entire file ─────────────────────────────
        vad_filter=False,

        # ── Hallucination prevention ──────────────────────────────────────
        condition_on_previous_text=False,   # prevents feedback loops
        temperature=[0.0, 0.2, 0.4, 0.6, 0.8, 1.0],  # auto-retry on repetition
        compression_ratio_threshold=2.4,    # reject absurdly repetitive segments
        no_speech_threshold=0.95,           # only skip if 95% sure there's NO speech
        log_prob_threshold=-1.5,            # accept lower-confidence chunks
    )

    language     = info.language
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
        f"✅ Done: {len(segments)} segments kept "
        f"(raw={len(raw)}, removed={len(raw) - len(segments)})"
    )
    return {
        "language":             language,
        "language_probability": language_prob,
        "segments":             segments,
    }
