/**
 * App.jsx — Root application component.
 *
 * State machine:
 *   'idle'       → show UploadForm
 *   'processing' → show ProgressTracker (poll backend every 1.5 s)
 *   'complete'   → show AudioPlayer + LyricsDisplay
 *   'error'      → show error + reset button
 *
 * All AI heavy-lifting happens on the Python backend.
 * The frontend only manages UI state + polls /api/status/{job_id}.
 */

import { useState, useRef, useCallback, useEffect } from 'react'
import UploadForm      from './components/UploadForm.jsx'
import ProgressTracker from './components/ProgressTracker.jsx'
import AudioPlayer     from './components/AudioPlayer.jsx'
import LyricsDisplay   from './components/LyricsDisplay.jsx'
import { uploadFile, uploadUrl, getStatus, getAudioUrl } from './utils/api.js'

const POLL_INTERVAL_MS = 1500  // how often to poll for status updates

export default function App() {
  // ── Global app state ────────────────────────────────────────────────────
  const [phase,        setPhase]        = useState('idle')   // idle | processing | complete | error
  const [jobId,        setJobId]        = useState(null)
  const [jobStatus,    setJobStatus]    = useState({})
  const [result,       setResult]       = useState(null)     // final lyric data
  const [currentTime,  setCurrentTime]  = useState(0)        // audio playback position (seconds)
  const [globalError,  setGlobalError]  = useState(null)

  const pollRef = useRef(null)  // interval handle

  // ── Start polling for job progress ───────────────────────────────────────
  const startPolling = useCallback((id) => {
    if (pollRef.current) clearInterval(pollRef.current)

    pollRef.current = setInterval(async () => {
      try {
        const data = await getStatus(id)
        setJobStatus(data)

        if (data.status === 'complete') {
          clearInterval(pollRef.current)
          setResult(data.result)
          setPhase('complete')
        } else if (data.status === 'error') {
          clearInterval(pollRef.current)
          setGlobalError(data.error || 'An unknown error occurred.')
          setPhase('error')
        }
      } catch (err) {
        // Don't stop polling on transient network errors
        console.warn('Poll error:', err.message)
      }
    }, POLL_INTERVAL_MS)
  }, [])

  // Clean up polling on unmount
  useEffect(() => () => clearInterval(pollRef.current), [])

  // ── Handle form submission ───────────────────────────────────────────────
  const handleSubmit = useCallback(async ({ file, url, title, artist, mode, onUploadProgress }) => {
    try {
      setPhase('processing')
      setGlobalError(null)
      setJobStatus({ status: 'processing', progress: 2, step: 'Uploading' })

      let response
      if (mode === 'file') {
        response = await uploadFile(file, title, artist, onUploadProgress)
      } else {
        response = await uploadUrl(url, title, artist)
      }

      const id = response.job_id
      setJobId(id)
      startPolling(id)
    } catch (err) {
      const msg = err.response?.data?.detail || err.message || 'Upload failed'
      setGlobalError(msg)
      setPhase('error')
    }
  }, [startPolling])

  // ── Reset to upload screen ───────────────────────────────────────────────
  const handleReset = () => {
    clearInterval(pollRef.current)
    setPhase('idle')
    setJobId(null)
    setJobStatus({})
    setResult(null)
    setCurrentTime(0)
    setGlobalError(null)
  }

  // ── Derived values ───────────────────────────────────────────────────────
  const audioUrl = jobId ? getAudioUrl(jobId) : null
  const segments = result?.segments  || []
  const waveform = result?.waveform  || []
  const meta     = result?.metadata  || {}

  // ─────────────────────────────────────────────────────────────────────────
  return (
    <div className="min-h-screen flex flex-col">
      {/* ── Header ── */}
      <header className="px-6 py-5 flex items-center justify-between border-b border-white/5">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-brand-600 to-purple-600 flex items-center justify-center text-lg shadow-lg shadow-brand-900/50">
            🎶
          </div>
          <div>
            <h1 className="text-lg font-bold gradient-text">LyricTranslate AI</h1>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {phase !== 'idle' && (
            <button onClick={handleReset} className="btn-secondary text-sm">
              ↩ New Song
            </button>
          )}
          {/* Language badge */}
          {meta.language && (
            <span className="text-xs px-3 py-1 bg-brand-900/40 border border-brand-700/30 rounded-full text-brand-300 font-medium">
              {meta.language?.toUpperCase()} → EN
            </span>
          )}
        </div>
      </header>

      {/* ── Main content ── */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 pt-8 pb-12">

        {/* ── IDLE: show upload form ── */}
        {phase === 'idle' && (
          <div className="max-w-2xl mx-auto space-y-6">
            {/* Hero text */}
            <div className="text-center mb-8 animate-fade-in">
              <h2 className="text-4xl font-extrabold mb-3">
                <span className="gradient-text">Live Karaoke Translations</span>
              </h2>
              <p className="text-gray-400 text-lg max-w-lg mx-auto leading-relaxed">
                Upload any song — from Bad Bunny to BTS — and watch real-time English translations
                dance in sync as the music plays.
              </p>
              <div className="flex gap-3 justify-center mt-4 flex-wrap">
                {['🇪🇸 Spanish','🇧🇷 Portuguese','🇫🇷 French','🇰🇷 Korean','🇯🇵 Japanese'].map((l) => (
                  <span key={l} className="text-xs px-3 py-1 bg-surface-800 border border-white/8 rounded-full text-gray-300">{l}</span>
                ))}
              </div>
            </div>
            <UploadForm onSubmit={handleSubmit} isLoading={false} />
          </div>
        )}

        {/* ── PROCESSING: show progress tracker ── */}
        {phase === 'processing' && (
          <div className="max-w-2xl mx-auto space-y-6">
            <ProgressTracker
              step={jobStatus.step}
              progress={jobStatus.progress}
              status={jobStatus.status}
              error={jobStatus.error}
            />

            {/* Fun tips while waiting */}
            <div className="glass p-5 text-center">
              <p className="text-sm text-gray-400">
                💡 <span className="text-gray-300 font-medium">Did you know?</span>{' '}
                Demucs uses AI trained on thousands of songs to cleanly separate vocals from
                instrumentals — even for heavily compressed MP3s.
              </p>
            </div>
          </div>
        )}

        {/* ── ERROR ── */}
        {phase === 'error' && (
          <div className="max-w-lg mx-auto glass p-10 text-center animate-fade-in">
            <div className="text-5xl mb-4">😕</div>
            <h3 className="text-xl font-bold text-white mb-2">Something went wrong</h3>
            <p className="text-sm text-red-400 mb-6 break-words">{globalError}</p>
            <button onClick={handleReset} className="btn-primary">
              Try Again
            </button>
          </div>
        )}

        {/* ── COMPLETE: player + lyrics ── */}
        {phase === 'complete' && result && (
          <div className="space-y-6 animate-fade-in">
            {/* Audio player */}
            <AudioPlayer
              audioUrl={audioUrl}
              waveformData={waveform}
              onTimeUpdate={setCurrentTime}
              metadata={meta}
            />

            {/* Lyrics display */}
            <LyricsDisplay
              segments={segments}
              currentTime={currentTime}
              metadata={meta}
            />
          </div>
        )}
      </main>

      {/* ── Footer ── */}
      <footer className="py-5 border-t border-white/5 text-center">
        <p className="text-xs text-gray-600">LyricTranslate AI</p>
      </footer>
    </div>
  )
}
