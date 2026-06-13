"""
jobs_store.py — Thread-safe in-memory job store.

Every processing job gets a UUID and is stored here.  Background threads
(Demucs, Whisper, Claude) write progress updates to this dict; the
frontend polls GET /api/status/{job_id} to read them.
"""

import threading
from typing import Any, Dict, Optional

# The global job registry — maps job_id → job dict
jobs: Dict[str, Dict[str, Any]] = {}

# A simple re-entrant lock so background threads can safely update jobs
_lock = threading.RLock()


# ─── Step labels ─────────────────────────────────────────────────────────────
STEP_UPLOADING   = "Uploading"
STEP_ISOLATING   = "Isolating Vocals"
STEP_TRANSCRIBING = "Transcribing"
STEP_TRANSLATING = "Translating"
STEP_SYNCING     = "Syncing Lyrics"
STEP_READY       = "Ready"


# ─── CRUD ────────────────────────────────────────────────────────────────────

def create_job(job_id: str, metadata: Optional[Dict] = None) -> Dict:
    """
    Initialise a new job entry with default values.
    Call this immediately after the file is received.
    """
    job = {
        "id":          job_id,
        "status":      "processing",   # processing | complete | error
        "progress":    0,              # 0–100
        "step":        STEP_UPLOADING,
        "error":       None,
        "result":      None,           # final lyric JSON (when complete)
        "file_path":   None,           # local path to uploaded audio
        "vocals_path": None,           # path to isolated vocals
        "segments":    None,           # raw Whisper segments
        "waveform":    None,           # downsampled amplitude array for WaveformPlayer
        "metadata":    metadata or {}, # title, artist, language, etc.
    }
    with _lock:
        jobs[job_id] = job
    return job


def update_job(job_id: str, **kwargs) -> None:
    """
    Update any fields on an existing job.
    Safe to call from background threads.
    """
    with _lock:
        if job_id in jobs:
            jobs[job_id].update(kwargs)


def get_job(job_id: str) -> Optional[Dict]:
    """Return the full job dict, or None if unknown."""
    with _lock:
        job = jobs.get(job_id)
        # Return a shallow copy so callers can't accidentally mutate shared state
        return dict(job) if job else None


def set_error(job_id: str, message: str) -> None:
    """Mark a job as failed with an error message."""
    update_job(job_id, status="error", error=message)


def set_complete(job_id: str, result: Any) -> None:
    """Mark a job as complete with the final lyrics result."""
    update_job(
        job_id,
        status="complete",
        progress=100,
        step=STEP_READY,
        result=result,
    )
