"""
routes/sync.py — POST /api/sync-lyrics + GET /api/status/{job_id}

sync-lyrics: Manually trigger the final merging step (assemble segments into result JSON).
status:      Poll for real-time job progress — the frontend polls this every 1.5 s.
"""

import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

import jobs_store as store

logger = logging.getLogger(__name__)
router = APIRouter()


# ─── POST /api/sync-lyrics ───────────────────────────────────────────────────

class SyncRequest(BaseModel):
    job_id: str


@router.post("/sync-lyrics")
async def sync_lyrics(body: SyncRequest):
    """
    Manually assemble the final lyric JSON from whatever segments are in the job.
    Useful if you want to merge partial results without re-running the whole pipeline.
    """
    job = store.get_job(body.job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")

    segments = job.get("segments")
    if not segments:
        raise HTTPException(status_code=400, detail="No segments to sync — run transcription first.")

    store.update_job(body.job_id, progress=92, step=store.STEP_SYNCING)

    result_segments = []
    for seg in segments:
        result_segments.append({
            "id":         seg.get("id", 0),
            "time":       seg.get("start", seg.get("time", 0.0)),
            "duration":   seg.get("duration", 3.0),
            "original":   seg.get("text", ""),
            "translated": seg.get("translated", seg.get("text", "")),
            "language":   seg.get("language", ""),
        })

    result = {
        "job_id":   body.job_id,
        "metadata": job.get("metadata", {}),
        "waveform": job.get("waveform", []),
        "segments": result_segments,
    }

    store.set_complete(body.job_id, result)
    return result


# ─── GET /api/status/{job_id} ────────────────────────────────────────────────

@router.get("/status/{job_id}")
async def get_status(job_id: str):
    """
    Return the current state of a processing job.

    Response shape:
    {
        "id":       "...",
        "status":   "processing" | "complete" | "error",
        "progress": 0–100,
        "step":     "Isolating Vocals",
        "error":    null | "...",
        "result":   null | { full lyric object }
    }
    """
    job = store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")

    # Only send result payload when complete (avoids sending large dict on every poll)
    return {
        "id":       job["id"],
        "status":   job["status"],
        "progress": job["progress"],
        "step":     job["step"],
        "error":    job.get("error"),
        "result":   job.get("result") if job["status"] == "complete" else None,
    }


# ─── GET /api/audio/{job_id} ─────────────────────────────────────────────────

from fastapi.responses import FileResponse
from pathlib import Path

@router.get("/audio/{job_id}")
async def stream_audio(job_id: str):
    """
    Stream the original uploaded audio file for the AudioPlayer.
    """
    job = store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")

    file_path = job.get("file_path")
    if not file_path or not Path(file_path).exists():
        raise HTTPException(status_code=404, detail="Audio file not found.")

    return FileResponse(
        path=file_path,
        media_type="audio/mpeg",
        headers={"Accept-Ranges": "bytes"},
    )
