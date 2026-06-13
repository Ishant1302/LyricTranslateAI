/**
 * AudioPlayer.jsx — Custom dark-mode audio player with waveform visualisation.
 *
 * Features:
 *  • HTML5 <audio> element for playback (no third-party player libraries)
 *  • Canvas waveform rendered from server-provided amplitude data
 *  • Play / pause, seek (click on waveform), volume slider, time display
 *  • Exposes currentTime to parent via onTimeUpdate so LyricsDisplay can sync
 */

import { useState, useRef, useEffect, useCallback } from 'react'
import { Play, Pause, Volume2, VolumeX } from 'lucide-react'

/** Format seconds as MM:SS */
function fmt(secs) {
  const m = Math.floor(secs / 60)
  const s = Math.floor(secs % 60)
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
}

export default function AudioPlayer({ audioUrl, waveformData = [], onTimeUpdate, metadata = {} }) {
  const audioRef   = useRef(null)
  const canvasRef  = useRef(null)
  const animRef    = useRef(null)

  const [isPlaying,  setIsPlaying]  = useState(false)
  const [currentTime, setCurrentTime] = useState(0)
  const [duration,   setDuration]   = useState(0)
  const [volume,     setVolume]     = useState(1)
  const [muted,      setMuted]      = useState(false)

  // ── Draw waveform on canvas ──────────────────────────────────────────────
  const drawWaveform = useCallback(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    const W = canvas.width
    const H = canvas.height
    ctx.clearRect(0, 0, W, H)

    const data = waveformData.length > 0 ? waveformData : Array.from({ length: 100 }, () => Math.random() * 0.4 + 0.1)
    const barW = W / data.length
    const progress = duration > 0 ? currentTime / duration : 0

    data.forEach((amp, i) => {
      const x   = i * barW
      const barH = Math.max(3, amp * H * 0.85)
      const y   = (H - barH) / 2
      const pct = i / data.length

      if (pct < progress) {
        // Played portion — bright brand gradient
        const grad = ctx.createLinearGradient(0, y, 0, y + barH)
        grad.addColorStop(0, '#8195f7')
        grad.addColorStop(1, '#a78bfa')
        ctx.fillStyle = grad
      } else {
        // Unplayed — dimmer
        ctx.fillStyle = 'rgba(255,255,255,0.12)'
      }

      ctx.beginPath()
      ctx.roundRect(x + 1, y, Math.max(1, barW - 2), barH, 2)
      ctx.fill()
    })
  }, [waveformData, currentTime, duration])

  useEffect(() => {
    drawWaveform()
  }, [drawWaveform])

  // ── Audio event listeners ────────────────────────────────────────────────
  useEffect(() => {
    const audio = audioRef.current
    if (!audio) return

    const onLoaded = () => setDuration(audio.duration || 0)
    const onTime   = () => {
      setCurrentTime(audio.currentTime)
      onTimeUpdate?.(audio.currentTime)
    }
    const onEnded  = () => setIsPlaying(false)

    audio.addEventListener('loadedmetadata', onLoaded)
    audio.addEventListener('timeupdate', onTime)
    audio.addEventListener('ended', onEnded)

    return () => {
      audio.removeEventListener('loadedmetadata', onLoaded)
      audio.removeEventListener('timeupdate', onTime)
      audio.removeEventListener('ended', onEnded)
    }
  }, [onTimeUpdate])

  // ── Playback controls ────────────────────────────────────────────────────
  const togglePlay = () => {
    const audio = audioRef.current
    if (!audio) return
    if (isPlaying) audio.pause()
    else           audio.play()
    setIsPlaying(!isPlaying)
  }

  const handleSeek = (e) => {
    const audio = audioRef.current
    if (!audio || !duration) return
    const rect = e.currentTarget.getBoundingClientRect()
    const pct  = (e.clientX - rect.left) / rect.width
    audio.currentTime = pct * duration
  }

  const handleVolume = (e) => {
    const v = parseFloat(e.target.value)
    setVolume(v)
    if (audioRef.current) audioRef.current.volume = v
    setMuted(v === 0)
  }

  const toggleMute = () => {
    const audio = audioRef.current
    if (!audio) return
    audio.muted = !muted
    setMuted(!muted)
  }

  const progress = duration > 0 ? (currentTime / duration) * 100 : 0

  return (
    <div className="glass p-6 animate-slide-up">
      {/* Song info */}
      <div className="flex items-center gap-4 mb-5">
        {/* Album art placeholder */}
        <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-brand-700 to-purple-800 flex items-center justify-center shrink-0 text-xl shadow-lg">
          🎵
        </div>
        <div className="min-w-0">
          <p className="font-semibold text-white truncate">{metadata.title || 'Unknown Song'}</p>
          <p className="text-sm text-gray-400 truncate">{metadata.artist || 'Unknown Artist'}</p>
        </div>
        <div className="ml-auto text-xs font-mono text-gray-500">
          {fmt(currentTime)} / {fmt(duration)}
        </div>
      </div>

      {/* Waveform canvas — click to seek */}
      <div
        className="relative cursor-pointer mb-4 select-none"
        onClick={handleSeek}
        title="Click to seek"
      >
        <canvas
          ref={canvasRef}
          width={800}
          height={64}
          className="w-full h-12 rounded-lg"
        />
        {/* Playhead needle */}
        <div
          className="absolute top-0 bottom-0 w-0.5 bg-white/70 rounded-full pointer-events-none transition-none"
          style={{ left: `${progress}%` }}
        />
      </div>

      {/* Controls row */}
      <div className="flex items-center gap-4">
        {/* Play / Pause */}
        <button
          onClick={togglePlay}
          className="w-11 h-11 rounded-full bg-brand-600 hover:bg-brand-500 flex items-center justify-center 
                     shadow-lg shadow-brand-900/50 transition-all duration-200 hover:scale-105 active:scale-95 shrink-0"
        >
          {isPlaying
            ? <Pause  className="w-5 h-5 text-white" />
            : <Play   className="w-5 h-5 text-white ml-0.5" />}
        </button>

        {/* Seek bar */}
        <div className="flex-1">
          <input
            type="range"
            min={0}
            max={duration || 100}
            value={currentTime}
            step={0.1}
            onChange={(e) => {
              if (audioRef.current)
                audioRef.current.currentTime = parseFloat(e.target.value)
            }}
            className="w-full"
            style={{
              background: `linear-gradient(to right, #8195f7 ${progress}%, rgba(255,255,255,0.12) ${progress}%)`,
            }}
          />
        </div>

        {/* Volume */}
        <button onClick={toggleMute} className="text-gray-400 hover:text-white transition-colors">
          {muted || volume === 0
            ? <VolumeX className="w-4 h-4" />
            : <Volume2 className="w-4 h-4" />}
        </button>
        <input
          type="range"
          min={0}
          max={1}
          step={0.01}
          value={muted ? 0 : volume}
          onChange={handleVolume}
          className="w-20"
          style={{
            background: `linear-gradient(to right, #8195f7 ${(muted ? 0 : volume) * 100}%, rgba(255,255,255,0.12) ${(muted ? 0 : volume) * 100}%)`,
          }}
        />
      </div>

      {/* Hidden audio element */}
      <audio ref={audioRef} src={audioUrl} preload="metadata" />
    </div>
  )
}
