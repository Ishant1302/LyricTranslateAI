# 🎶 LyricTranslate AI

> **AI-powered karaoke lyrics translator** — Upload any song and watch real-time English translations sync to the music like live subtitles!.

Built with **FastAPI + React**, powered by **Claude AI**, **OpenAI Whisper**, and **Demucs**.

---

## ✨ Features

| Feature | Details |
|---|---|
| 🎤 Vocal Isolation | Demucs separates vocals from instruments |
| 🎙️ Transcription | faster-whisper detects language + timestamps |
| 🤖 Translation | Claude API preserves slang, idioms & rhyme |
| 🎵 Karaoke Display | Live line highlighting synced to playback |
| 📤 Export | SRT subtitle file or plain-text |
| 🔗 URL Support | Paste YouTube / SoundCloud links |
| 💾 Caching | Never re-process the same song twice |

---

## 🚀 Quick Start

### Prerequisites

- **Python 3.10+**
- **Node.js 18+**
- **FFmpeg** installed and on PATH *(required by Demucs & yt-dlp)*
  - Windows: `winget install Gyan.FFmpeg` or download from [ffmpeg.org](https://ffmpeg.org)
- **An Anthropic API key** → [console.anthropic.com](https://console.anthropic.com)

---

### 1. Clone & Set Up

```bash
git clone <repo-url>
cd lyrictranslate-ai
```

### 2. Backend Setup

```bash
cd backend

# Copy .env and fill in your API key
copy .env.example .env
# Edit .env — set ANTHROPIC_API_KEY=sk-ant-...

# Create a virtual environment (recommended)
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # Mac/Linux

# Install dependencies
pip install -r requirements.txt
```

> ⚠️ **First run note:** Demucs (~700 MB) and Whisper (~150 MB for base model) models
> are downloaded automatically on first use. This may take a few minutes.

### 3. Frontend Setup

```bash
cd ../frontend
npm install
```

### 4. Run the App

**Terminal 1 — Backend:**
```bash
cd backend
venv\Scripts\activate
uvicorn main:app --reload
```

**Terminal 2 — Frontend:**
```bash
cd frontend
npm run dev
```

Open **http://localhost:5173** in your browser 🎉

---

## 📁 Project Structure

```
lyrictranslate-ai/
├── backend/
│   ├── main.py                  # FastAPI app entry point
│   ├── jobs_store.py            # In-memory job tracker
│   ├── routes/
│   │   ├── upload.py            # POST /api/upload (+ full pipeline)
│   │   ├── transcribe.py        # POST /api/transcribe
│   │   ├── translate.py         # POST /api/translate
│   │   └── sync.py              # POST /api/sync-lyrics + GET /api/status/{id}
│   ├── services/
│   │   ├── demucs_service.py    # Vocal isolation (Demucs)
│   │   ├── whisper_service.py   # Speech-to-text (faster-whisper)
│   │   └── claude_service.py    # Translation (Claude API)
│   ├── uploads/                 # Uploaded audio files (auto-created)
│   ├── cache/                   # Translated lyric cache (auto-created)
│   ├── requirements.txt
│   └── .env.example
└── frontend/
    ├── src/
    │   ├── App.jsx              # Root component + state machine
    │   ├── components/
    │   │   ├── AudioPlayer.jsx  # Custom player + waveform canvas
    │   │   ├── LyricsDisplay.jsx # Karaoke dual-column view
    │   │   ├── UploadForm.jsx   # Drag-drop upload + URL input
    │   │   └── ProgressTracker.jsx # 5-step pipeline indicator
    │   └── utils/
    │       ├── api.js           # Axios helpers
    │       └── export.js        # SRT/TXT/clipboard export
    ├── package.json
    ├── vite.config.js
    └── tailwind.config.js
```

---

## 🔌 API Reference

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/upload` | Upload file or URL, start pipeline → `{job_id}` |
| `GET`  | `/api/status/{job_id}` | Poll processing progress |
| `GET`  | `/api/audio/{job_id}` | Stream audio to the player |
| `POST` | `/api/transcribe` | Re-run Whisper on a job |
| `POST` | `/api/translate` | Re-run Claude translation on a job |
| `POST` | `/api/sync-lyrics` | Manually merge segments into result |

### Lyric Segment Format

```json
{
  "id": 0,
  "time": 12.5,
  "duration": 3.2,
  "original": "Yo perreo sola",
  "translated": "I twerk alone",
  "language": "es"
}
```

---

## ⚙️ Configuration (`.env`)

| Variable | Default | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | *(required)* | Your Claude API key |
| `WHISPER_MODEL_SIZE` | `base` | `tiny` / `base` / `small` / `medium` / `large-v3` |
| `DEMUCS_MODEL` | `htdemucs` | Demucs model variant |
| `FRONTEND_ORIGIN` | `http://localhost:5173` | CORS allowed origin |

---

## 🐌 Performance Notes

- **Vocal isolation (Demucs)** is CPU-intensive. A 3-min song takes ~5-10 min on CPU.
  → For faster results: use a shorter audio clip, or enable GPU (`CUDA`).
- **Whisper** runs in ~1-2× real-time on CPU.
- **Claude** translation is fast (~3-5 s for a full song).
- **Caching** is MD5-based — re-uploading the same file returns instantly.

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 18 + Vite + Tailwind CSS |
| Backend | FastAPI (Python 3.10+) |
| Vocal AI | Demucs (htdemucs) by Meta Research |
| Transcription | faster-whisper (OpenAI Whisper CTranslate2) |
| Translation | Claude 3.5 Sonnet via Anthropic API |
| URL Download | yt-dlp |

---

## 📄 License

MIT — build something amazing! 🚀
