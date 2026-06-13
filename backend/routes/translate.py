"""
routes/translate.py — POST /api/translate

Stand-alone endpoint to (re)run Claude translation on an existing job's segments.
"""

import logging
import asyncio
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

import jobs_store as store
from services import claude_service

logger = logging.getLogger(__name__)
router = APIRouter()


class TranslateRequest(BaseModel):
    job_id: str


@router.post("/translate")
async def translate(body: TranslateRequest, request: Request):
    """
    Re-run Claude translation on the Whisper segments for *job_id*.
    The job must already have segments set (i.e. transcription must be done).
    """
    job = store.get_job(body.job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")

    segments = job.get("segments")
    if not segments:
        raise HTTPException(
            status_code=400,
            detail="No segments found. Run transcription first via POST /api/transcribe.",
        )

    language = (job.get("metadata") or {}).get("language", "auto")
    store.update_job(body.job_id, status="processing", progress=72, step=store.STEP_TRANSLATING)

    def _translate():
        def progress_cb(pct):
            store.update_job(body.job_id, progress=int(72 + pct * 0.18))

        try:
            translated = claude_service.translate_segments(
                segments, source_language=language, progress_callback=progress_cb
            )
            store.update_job(body.job_id, segments=translated, progress=90, step=store.STEP_SYNCING)
        except Exception as e:
            store.set_error(body.job_id, f"Translation failed: {e}")

    executor = request.app.state.executor
    loop = asyncio.get_event_loop()
    loop.run_in_executor(executor, _translate)

    return {"job_id": body.job_id, "status": "translating"}
