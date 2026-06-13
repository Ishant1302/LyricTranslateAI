/**
 * UploadForm.jsx — Drag-and-drop audio upload + URL paste form.
 *
 * Features:
 *  • Drag-and-drop file zone (highlights on hover)
 *  • Click-to-browse fallback
 *  • OR paste a YouTube/SoundCloud/Spotify URL
 *  • Optional song title + artist fields
 *  • Animated upload progress bar
 */

import { useState, useRef, useCallback } from 'react'
import { Upload, Link, Music, User, FileAudio } from 'lucide-react'

export default function UploadForm({ onSubmit, isLoading }) {
  const [dragOver,    setDragOver]    = useState(false)
  const [file,        setFile]        = useState(null)
  const [url,         setUrl]         = useState('')
  const [title,       setTitle]       = useState('')
  const [artist,      setArtist]      = useState('')
  const [mode,        setMode]        = useState('file') // 'file' | 'url'
  const [uploadPct,   setUploadPct]   = useState(0)
  const fileInputRef = useRef(null)

  // ── Drag & drop ──────────────────────────────────────────────────────────
  const handleDragOver = useCallback((e) => {
    e.preventDefault()
    setDragOver(true)
  }, [])

  const handleDragLeave = useCallback(() => setDragOver(false), [])

  const handleDrop = useCallback((e) => {
    e.preventDefault()
    setDragOver(false)
    const dropped = e.dataTransfer.files[0]
    if (dropped) setFile(dropped)
  }, [])

  const handleFileChange = (e) => {
    if (e.target.files[0]) setFile(e.target.files[0])
  }

  // ── Submit ───────────────────────────────────────────────────────────────
  const handleSubmit = (e) => {
    e.preventDefault()
    if (mode === 'file' && !file) return
    if (mode === 'url'  && !url)  return
    setUploadPct(0)
    onSubmit({ file, url, title, artist, mode, onUploadProgress: setUploadPct })
  }

  const canSubmit = !isLoading && (mode === 'file' ? !!file : !!url)

  return (
    <div className="glass p-8 animate-fade-in">
      {/* Header */}
      <div className="flex items-center gap-3 mb-7">
        <div className="w-10 h-10 rounded-xl bg-brand-700/40 flex items-center justify-center">
          <Music className="w-5 h-5 text-brand-300" />
        </div>
        <div>
          <h2 className="text-lg font-semibold text-white">Add a Song</h2>
          <p className="text-sm text-gray-400">Upload an audio file or paste a URL to get started</p>
        </div>
      </div>

      {/* Mode toggle */}
      <div className="flex gap-2 mb-6 p-1 bg-surface-800 rounded-xl w-fit">
        {['file', 'url'].map((m) => (
          <button
            key={m}
            onClick={() => setMode(m)}
            className={`px-5 py-2 rounded-lg text-sm font-medium transition-all duration-200 ${
              mode === m
                ? 'bg-brand-600 text-white shadow-lg shadow-brand-900/50'
                : 'text-gray-400 hover:text-white'
            }`}
          >
            {m === 'file' ? '📁 File Upload' : '🔗 URL'}
          </button>
        ))}
      </div>

      <form onSubmit={handleSubmit} className="space-y-5">
        {/* ── File drop zone ── */}
        {mode === 'file' && (
          <div
            className={`drop-zone rounded-2xl p-10 flex flex-col items-center gap-4 cursor-pointer
              ${dragOver ? 'drag-over' : ''}
              ${file ? 'border-brand-500/60 bg-brand-900/10' : ''}`}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept=".mp3,.wav,.flac,.ogg,.m4a,.aac"
              className="hidden"
              onChange={handleFileChange}
            />
            {file ? (
              <>
                <div className="w-14 h-14 rounded-2xl bg-brand-700/30 flex items-center justify-center">
                  <FileAudio className="w-7 h-7 text-brand-300" />
                </div>
                <div className="text-center">
                  <p className="font-semibold text-white">{file.name}</p>
                  <p className="text-sm text-gray-400 mt-1">
                    {(file.size / 1024 / 1024).toFixed(1)} MB
                  </p>
                </div>
                <p className="text-xs text-brand-400">Click to change file</p>
              </>
            ) : (
              <>
                <div className="w-14 h-14 rounded-2xl bg-surface-700 flex items-center justify-center">
                  <Upload className="w-7 h-7 text-gray-400" />
                </div>
                <div className="text-center">
                  <p className="font-medium text-white">Drop your audio here</p>
                  <p className="text-sm text-gray-400 mt-1">MP3, WAV, FLAC, OGG, M4A supported</p>
                </div>
                <p className="text-xs text-brand-400 border border-brand-700/30 px-3 py-1 rounded-full">
                  Browse files
                </p>
              </>
            )}
          </div>
        )}

        {/* ── URL input ── */}
        {mode === 'url' && (
          <div className="relative">
            <Link className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
            <input
              type="url"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://youtube.com/watch?v=... or SoundCloud link"
              className="w-full bg-surface-800 border border-white/8 rounded-xl pl-11 pr-4 py-3.5
                         text-white placeholder-gray-500 focus:outline-none focus:border-brand-500/60
                         focus:ring-2 focus:ring-brand-500/20 transition-all"
            />
          </div>
        )}

        {/* ── Optional metadata ── */}
        <div className="grid grid-cols-2 gap-4">
          <div className="relative">
            <Music className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Song title (optional)"
              className="w-full bg-surface-800 border border-white/8 rounded-xl pl-11 pr-4 py-3
                         text-white placeholder-gray-500 focus:outline-none focus:border-brand-500/60
                         focus:ring-2 focus:ring-brand-500/20 transition-all text-sm"
            />
          </div>
          <div className="relative">
            <User className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
            <input
              type="text"
              value={artist}
              onChange={(e) => setArtist(e.target.value)}
              placeholder="Artist name (optional)"
              className="w-full bg-surface-800 border border-white/8 rounded-xl pl-11 pr-4 py-3
                         text-white placeholder-gray-500 focus:outline-none focus:border-brand-500/60
                         focus:ring-2 focus:ring-brand-500/20 transition-all text-sm"
            />
          </div>
        </div>

        {/* ── Upload progress bar (visible after submit) ── */}
        {isLoading && uploadPct > 0 && uploadPct < 100 && (
          <div>
            <div className="flex justify-between text-xs text-gray-400 mb-1.5">
              <span>Uploading file…</span>
              <span>{uploadPct}%</span>
            </div>
            <div className="h-1.5 bg-surface-700 rounded-full overflow-hidden">
              <div
                className="h-full bg-gradient-to-r from-brand-600 to-brand-400 rounded-full transition-all duration-300"
                style={{ width: `${uploadPct}%` }}
              />
            </div>
          </div>
        )}

        {/* ── Submit button ── */}
        <button
          type="submit"
          disabled={!canSubmit}
          className={`btn-primary w-full flex items-center justify-center gap-2
            ${!canSubmit ? 'opacity-40 cursor-not-allowed pointer-events-none' : ''}`}
        >
          {isLoading ? (
            <>
              <div className="spinner w-5 h-5" />
              Processing…
            </>
          ) : (
            <>
              <Music className="w-5 h-5" />
              Translate Lyrics
            </>
          )}
        </button>
      </form>
    </div>
  )
}
