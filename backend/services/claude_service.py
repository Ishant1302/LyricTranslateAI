"""
services/claude_service.py — Lyric translation via Google's public HTTP API.

Batches multiple lyric lines into a single request (separated by newlines) to
dramatically reduce the number of HTTP calls and avoid Google's rate-limiter
cutting out mid-song.

Strategy
--------
1. Group segments into batches of BATCH_SIZE lines.
2. Join with '\\n', translate the whole block in one call.
3. Split result back on '\\n' — if the count matches, assign directly.
4. If count mismatches (Google sometimes merges/drops blank lines), fall back
   to translating each segment individually.
5. Exponential back-off on 429 / connection errors.
"""

import time
import logging
import requests
from typing import List, Dict, Optional, Callable

logger = logging.getLogger(__name__)

GOOGLE_TRANSLATE_URL = "https://translate.googleapis.com/translate_a/single"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

BATCH_SIZE    = 20    # lines per request  — keeps URL short enough for GET
MAX_RETRIES   = 5
BASE_DELAY_S  = 2.0   # base back-off; doubles each retry
REQUEST_GAP_S = 0.3   # pause between batch calls


# ─── Low-level call ───────────────────────────────────────────────────────────

def _call_google(text: str, source: str, target: str = "en") -> str:
    """Single HTTP call to Google's public translate endpoint."""
    params = {
        "client": "gtx",
        "sl": source,
        "tl": target,
        "dt": "t",
        "q":  text,
    }
    resp = requests.get(
        GOOGLE_TRANSLATE_URL, params=params,
        headers=HEADERS, timeout=20,
    )
    resp.raise_for_status()
    data = resp.json()
    return "".join(seg[0] for seg in data[0] if seg and seg[0]).strip()


def _call_with_backoff(text: str, source: str, target: str = "en") -> str:
    """Wrap _call_google with exponential back-off on 429 / network errors."""
    delay = BASE_DELAY_S
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return _call_google(text, source, target)
        except requests.exceptions.HTTPError as exc:
            if exc.response is not None and exc.response.status_code == 429:
                logger.warning(f"Rate limited (429) — backing off {delay:.1f}s (attempt {attempt}/{MAX_RETRIES})")
                time.sleep(delay)
                delay = min(delay * 2, 30)
            else:
                raise
        except requests.exceptions.RequestException as exc:
            logger.warning(f"Network error attempt {attempt}/{MAX_RETRIES}: {exc}")
            if attempt < MAX_RETRIES:
                time.sleep(delay)
                delay = min(delay * 2, 30)
            else:
                raise
    raise RuntimeError("All retries exhausted")


# ─── Batch translation ────────────────────────────────────────────────────────

def _translate_batch(lines: List[str], source: str, target: str = "en") -> List[str]:
    """
    Translate a list of strings in a single API call.
    Falls back to per-line translation if the response line count doesn't match.
    """
    if not lines:
        return lines

    joined  = "\n".join(lines)
    try:
        result  = _call_with_backoff(joined, source, target)
        parts   = result.split("\n")

        if len(parts) == len(lines):
            return parts

        # Count mismatch — Google merged some lines. Fall back individually.
        logger.debug(f"Batch count mismatch ({len(parts)} vs {len(lines)}) — falling back to per-line")
    except Exception as exc:
        logger.warning(f"Batch translate failed: {exc} — falling back to per-line")

    # Per-line fallback
    results = []
    for line in lines:
        if not line.strip():
            results.append(line)
            continue
        try:
            translated = _call_with_backoff(line, source, target)
            results.append(translated if translated else line)
        except Exception as exc:
            logger.error(f"Per-line translate failed: {exc}")
            results.append(line)   # keep original on error
        time.sleep(REQUEST_GAP_S)
    return results


# ─── Public API ───────────────────────────────────────────────────────────────

def translate_segments(
    segments: List[Dict],
    source_language: str = "auto",
    progress_callback: Optional[Callable] = None,
) -> List[Dict]:
    """
    Translate all Whisper lyric segments to English.

    Parameters
    ----------
    segments        : list[dict] — each must have a 'text' key
    source_language : ISO 639-1 code from Whisper ('es', 'ko', 'fr' …)
    progress_callback : callable(float 0-100)
    """
    if not segments:
        return segments

    # Already English — pass through
    if source_language in ("en", "english"):
        logger.info("Source is English — no translation needed")
        if progress_callback:
            progress_callback(100)
        return [dict(s, translated=s.get("text", "")) for s in segments]

    total = len(segments)
    src   = source_language if source_language and source_language not in ("auto", "") else "auto"
    logger.info(f"🌐 Translating {total} segments in batches of {BATCH_SIZE}: '{src}' → 'en'")

    if progress_callback:
        progress_callback(2)

    # ── Build batch groups ────────────────────────────────────────────────────
    texts       = [seg.get("text", "").strip() for seg in segments]
    translated_texts: List[str] = [""] * total

    num_batches = (total + BATCH_SIZE - 1) // BATCH_SIZE
    for b_idx in range(num_batches):
        start = b_idx * BATCH_SIZE
        end   = min(start + BATCH_SIZE, total)
        batch = texts[start:end]

        logger.debug(f"Batch {b_idx+1}/{num_batches}: segments {start}–{end-1}")
        results = _translate_batch(batch, src)

        for i, translated in enumerate(results):
            translated_texts[start + i] = translated if translated else texts[start + i]

        # Progress: 2% → 96%
        if progress_callback:
            progress_callback(int(2 + (b_idx + 1) / num_batches * 94))

        # Pause between batches to be polite to Google's free endpoint
        if b_idx < num_batches - 1:
            time.sleep(REQUEST_GAP_S)

    # ── Second pass: retry any that came back unchanged (possible silent fail) ─
    unchanged = [i for i, (orig, tr) in enumerate(zip(texts, translated_texts))
                 if orig and tr.lower() == orig.lower()]

    if unchanged:
        logger.info(f"🔁 Second pass: {len(unchanged)} unchanged segments")
        for i in unchanged:
            if not texts[i]:
                continue
            try:
                translated = _call_with_backoff(texts[i], "auto")
                if translated and translated.lower() != texts[i].lower():
                    translated_texts[i] = translated
            except Exception as exc:
                logger.error(f"Second-pass failed for seg {i}: {exc}")
            time.sleep(REQUEST_GAP_S)

    if progress_callback:
        progress_callback(100)

    # ── Assemble result segments ──────────────────────────────────────────────
    result_segments = []
    for seg, translated in zip(segments, translated_texts):
        seg_copy = dict(seg)
        seg_copy["translated"] = translated if translated else seg.get("text", "")
        result_segments.append(seg_copy)

    still_untranslated = sum(
        1 for s in result_segments
        if s.get("text", "").strip().lower() == s.get("translated", "").strip().lower()
        and s.get("text", "").strip()
    )
    logger.info(
        f"✅ Translation done: {total - still_untranslated}/{total} segments translated"
        + (f" ({still_untranslated} unchanged — likely already English)" if still_untranslated else "")
    )
    return result_segments
