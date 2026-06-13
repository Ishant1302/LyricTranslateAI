"""
routes/transcribe.py — POST /api/transcribe

Stand-alone endpoint to (re)run Whisper transcription on an existing job's vocals.
Useful for testing or re-transcribing with a different model size without
re-uploading the file.
"""

import logging
import asyncio
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

import jobs_store as store
from services import whisper_service

logger = logging.getLogger(__name__)
router = APIRouter()


class TranscribeRequest(BaseModel):
    job_id: str


@router.post("/transcribe")
async def transcribe(body: TranscribeRequest, request: Request):
    """
    Re-run Whisper transcription on the isolated vocals for *job_id*.
    The job must already have a vocals_path set (i.e. Step 1 / isolate must be done).
    """
    job = store.get_job(body.job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")

    vocals_path = job.get("vocals_path") or job.get("file_path")
    if not vocals_path:
        raise HTTPException(
            status_code=400,
            detail="No audio path set. Upload a file first via POST /api/upload.",
        )

    store.update_job(body.job_id, status="processing", progress=42, step=store.STEP_TRANSCRIBING)

    def _transcribe():
        def progress_cb(pct):
            store.update_job(body.job_id, progress=int(42 + pct * 0.28))

        try:
            result = whisper_service.transcribe_audio(vocals_path, progress_callback=progress_cb)
            store.update_job(
                body.job_id,
                segments=result["segments"],
                progress=70,
                step=store.STEP_TRANSLATING,
            )
        except Exception as e:
            store.set_error(body.job_id, f"Transcription failed: {e}")

    executor = request.app.state.executor
    loop = asyncio.get_event_loop()
    loop.run_in_executor(executor, _transcribe)

    return {"job_id": body.job_id, "status": "transcribing"}
