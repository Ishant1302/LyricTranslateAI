"""
LyricTranslate AI - FastAPI Backend
Main entry point for the application.
"""

# Load .env FIRST so all services can read ANTHROPIC_API_KEY etc.
from dotenv import load_dotenv
load_dotenv()

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path

# Import all route modules
from routes import upload, transcribe, translate, sync


# ─── Lifespan (startup / shutdown) ─────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Creates a thread-pool executor on startup so we can run CPU-intensive ML tasks
    (Demucs, Whisper) in background threads without blocking FastAPI's event loop.
    """
    # 2 workers is usually enough for a local machine; bump up if you have more cores
    executor = ThreadPoolExecutor(max_workers=2)
    app.state.executor = executor

    # Make sure upload / cache directories exist
    Path("uploads").mkdir(exist_ok=True)
    Path("cache").mkdir(exist_ok=True)

    print("[OK] LyricTranslate AI backend started")
    yield  # app is running here

    executor.shutdown(wait=False)
    print("[STOP] Backend shutting down")


# ─── App creation ───────────────────────────────────────────────────────────
app = FastAPI(
    title="LyricTranslate AI",
    description="AI-powered karaoke-style lyrics translator",
    version="1.0.0",
    lifespan=lifespan,
)

# Allow requests from the Vite dev server (and production builds)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Vite default port
        "http://localhost:3000",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Routes ─────────────────────────────────────────────────────────────────
# All endpoints are prefixed with /api to make it easy to proxy from the frontend
app.include_router(upload.router,     prefix="/api", tags=["Upload"])
app.include_router(transcribe.router, prefix="/api", tags=["Transcribe"])
app.include_router(translate.router,  prefix="/api", tags=["Translate"])
app.include_router(sync.router,       prefix="/api", tags=["Sync"])


# ─── Health check ───────────────────────────────────────────────────────────
@app.get("/", tags=["Health"])
async def root():
    """Simple health-check endpoint."""
    return {"message": "LyricTranslate AI API is running 🎵", "version": "1.0.0"}


# ─── Dev entry point ────────────────────────────────────────────────────────
if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
