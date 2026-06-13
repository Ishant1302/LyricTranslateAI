"""
services/demucs_service.py — Vocal isolation using Demucs (by Facebook Research).

We chose Demucs over Spleeter because:
  • Spleeter requires old TensorFlow 2.x which conflicts on modern Windows/Python.
  • Demucs (htdemucs) produces significantly higher-quality vocal separation.
  • Demucs installs cleanly via pip on Python 3.10+.

The heavy lifting runs in a subprocess so it doesn't block the event loop.
"""

import os
import sys
import subprocess
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Demucs model to use — can be overridden via .env
DEMUCS_MODEL = os.getenv("DEMUCS_MODEL", "htdemucs")


def isolate_vocals(
    audio_path: str,
    output_dir: str,
    progress_callback=None,
) -> str:
    """
    Run Demucs vocal isolation on *audio_path*.

    Parameters
    ----------
    audio_path : str
        Absolute path to the input audio file (MP3, WAV, FLAC, …).
    output_dir : str
        Directory where Demucs will write its stems subdirectory.
    progress_callback : callable, optional
        Called with a float (0–100) whenever we have a progress estimate.

    Returns
    -------
    str
        Path to the extracted vocals WAV file.

    Raises
    ------
    RuntimeError
        If Demucs exits with a non-zero return code.
    """
    audio_path = str(Path(audio_path).resolve())
    output_dir = str(Path(output_dir).resolve())

    logger.info(f"[Demucs] Starting vocal isolation for: {audio_path}")
    if progress_callback:
        progress_callback(2)  # starting demucs

    # Build the subprocess command.
    # --two-stems vocals  → only produce vocals + no_vocals (faster than all 4 stems)
    # -n NAME             → model name (correct flag in demucs 4.x; NOT --model)
    # -o output_dir       → where to save output
    cmd = [
        sys.executable, "-m", "demucs",
        "--two-stems", "vocals",
        "-n", DEMUCS_MODEL,
        "-o", output_dir,
        audio_path,
    ]

    logger.debug(f"Demucs command: {' '.join(cmd)}")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=1800,  # 30-minute timeout (large files on CPU can be slow)
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError("Demucs timed out after 30 minutes — try a shorter audio file.")

    if result.returncode != 0:
        raise RuntimeError(
            f"Demucs failed (exit {result.returncode}):\n{result.stderr}"
        )

    if progress_callback:
        progress_callback(100)

    # Demucs writes to: output_dir/<model>/<stem_name>/vocals.wav
    stem_name = Path(audio_path).stem
    vocals_path = Path(output_dir) / DEMUCS_MODEL / stem_name / "vocals.wav"

    if not vocals_path.exists():
        # Fallback: search for any vocals.wav under output_dir
        candidates = list(Path(output_dir).rglob("vocals.wav"))
        if candidates:
            vocals_path = candidates[0]
        else:
            raise RuntimeError(
                f"Demucs finished but vocals.wav not found under {output_dir}.\n"
                f"Demucs stdout: {result.stdout}"
            )

    logger.info(f"[Demucs] Vocals isolated: {vocals_path}")
    return str(vocals_path)
