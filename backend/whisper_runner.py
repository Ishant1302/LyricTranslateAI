#!/usr/bin/env python3
"""
whisper_runner.py — Thin Python shim called by WhisperService.java

Usage:
    python whisper_runner.py <audio_path>

Outputs a single JSON object to stdout with the transcription result.
All logs/warnings go to stderr so they don't pollute the JSON output.

This script exists because faster-whisper is a Python-only library —
the Java backend invokes it via ProcessBuilder and parses the stdout JSON.
"""

import sys
import json
import os
import logging

# Redirect all logs to stderr — Java reads stdout for JSON only
logging.basicConfig(stream=sys.stderr, level=logging.WARNING)

def main():
    if len(sys.argv) < 2:
        json.dump({"error": "Usage: whisper_runner.py <audio_path>"}, sys.stdout)
        sys.exit(1)

    audio_path   = sys.argv[1]
    model_size   = os.getenv("WHISPER_MODEL_SIZE", "base")

    try:
        from faster_whisper import WhisperModel
    except ImportError:
        json.dump({"error": "faster-whisper not installed. Run: pip install faster-whisper"}, sys.stdout)
        sys.exit(1)

    print(f"[whisper_runner] Loading model '{model_size}'...", file=sys.stderr)
    model = WhisperModel(model_size, device="cpu", compute_type="int8")
    print(f"[whisper_runner] Transcribing: {audio_path}", file=sys.stderr)

    segments_iter, info = model.transcribe(
        audio_path,
        task="transcribe",

        # ── Speed settings (same as whisper_service.py) ────────────────────
        beam_size=2,
        temperature=[0.0, 0.4],

        # ── Accuracy / hallucination prevention ───────────────────────────
        vad_filter=False,
        condition_on_previous_text=False,
        compression_ratio_threshold=2.4,
        no_speech_threshold=0.80,
        log_prob_threshold=-1.5,
    )

    language      = info.language
    language_prob = round(info.language_probability, 3)
    print(f"[whisper_runner] Detected language: {language} ({language_prob:.1%})", file=sys.stderr)

    # ── Collect raw segments ───────────────────────────────────────────────
    raw = []
    for idx, seg in enumerate(segments_iter):
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

    # ── Hallucination cleaner (same logic as whisper_service.py) ──────────
    segments = _clean_segments(raw)
    print(f"[whisper_runner] {len(segments)} segments kept (raw={len(raw)})", file=sys.stderr)

    result = {
        "language":             language,
        "language_probability": language_prob,
        "segments":             segments,
    }

    # Output clean JSON to stdout — Java reads this
    json.dump(result, sys.stdout, ensure_ascii=False)


def _clean_segments(segments):
    """
    Remove hallucination loops.
    Mirrors _clean_segments() from whisper_service.py exactly.
    """
    if not segments:
        return segments

    # Pass 1: consecutive repeat filter (allow ≤2 back-to-back identical lines)
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

    return pass2


if __name__ == "__main__":
    main()
