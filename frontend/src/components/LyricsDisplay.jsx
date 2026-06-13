/**
 * LyricsDisplay.jsx — Spotify-style synchronized lyrics.
 *
 * Rules (per user spec):
 *  • Active line  → bold, pure white (#ffffff)
 *  • Past lines   → dim gray, fade away
 *  • Future lines → medium gray
 *  • NO boxes, NO glow, NO backgrounds, NO borders — just text weight/color
 *  • Active line always stays vertically centered while music plays
 */

import { useState, useRef, useEffect } from 'react'
import { Download, ChevronDown } from 'lucide-react'
import { downloadSRT, downloadTXT } from '../utils/export.js'

/** Find which segment is currently active based on playback time */
function findActiveIndex(segments, time) {
  if (!segments.length || time < 0) return -1
  for (let i = segments.length - 1; i >= 0; i--) {
    if (time >= segments[i].time) return i
  }
  return -1
}

export default function LyricsDisplay({ segments = [], currentTime = 0, metadata = {} }) {
  const [displayMode, setDisplayMode] = useState('both')
  const [showExport,  setShowExport]  = useState(false)

  const containerRef = useRef(null)
  const activeRef    = useRef(null)
  const activeIdx    = findActiveIndex(segments, currentTime)

  // ── Keep active line centered in the scroll container ───────────────────
  // scrollIntoView with block:'center' is the most reliable approach —
  // it works within the nearest scrollable ancestor (our container div).
  // We do NOT change font size per line, so there's zero layout shift
  // between lines, which keeps the scroll position perfectly accurate.
  useEffect(() => {
    if (activeRef.current) {
      activeRef.current.scrollIntoView({
        behavior: 'smooth',
        block: 'center',
      })
    }
  }, [activeIdx])

  if (segments.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-24 animate-fade-in">
        <div className="text-6xl mb-4">🎤</div>
        <p className="text-gray-500 text-lg">Lyrics will appear here once processing is complete.</p>
      </div>
    )
  }

  const filename = `${metadata.artist || 'artist'}_${metadata.title || 'song'}`.replace(/\s+/g, '_')

  return (
    <div className="flex flex-col animate-slide-up">

      {/* ── Toolbar ── */}
      <div className="flex items-center gap-3 pb-4 mb-2 border-b border-white/5">
        <div className="flex gap-1 p-1 bg-surface-800 rounded-xl text-xs">
          {[
            { value: 'both',       label: '⇄ Both'      },
            { value: 'original',   label: '💬 Original'  },
            { value: 'translated', label: '🇬🇧 English' },
          ].map((m) => (
            <button
              key={m.value}
              onClick={() => setDisplayMode(m.value)}
              className={`px-3 py-1.5 rounded-lg font-medium transition-all ${
                displayMode === m.value
                  ? 'bg-brand-600 text-white'
                  : 'text-gray-400 hover:text-white'
              }`}
            >
              {m.label}
            </button>
          ))}
        </div>

        <span className="text-xs text-gray-600">{segments.length} lines</span>

        <div className="ml-auto relative">
          <button
            onClick={() => setShowExport(!showExport)}
            className="btn-secondary flex items-center gap-2 text-xs px-3 py-2"
          >
            <Download className="w-3.5 h-3.5" />
            Export
            <ChevronDown className={`w-3 h-3 transition-transform ${showExport ? 'rotate-180' : ''}`} />
          </button>
          {showExport && (
            <div className="absolute right-0 top-10 z-50 glass rounded-xl p-2 min-w-44 shadow-2xl">
              {[
                { label: '⬇️ Download SRT', action: () => downloadSRT(segments, displayMode, filename) },
                { label: '⬇️ Download TXT', action: () => downloadTXT(segments, metadata, filename) },
              ].map((opt) => (
                <button
                  key={opt.label}
                  onClick={() => { opt.action(); setShowExport(false) }}
                  className="w-full text-left px-3 py-2 text-sm text-gray-300
                             hover:text-white hover:bg-surface-700 rounded-lg transition-colors"
                >
                  {opt.label}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* ── Lyrics scroll container ── */}
      <div
        ref={containerRef}
        style={{
          height: '60vh',
          overflowY: 'scroll',
          scrollbarWidth: 'none',   // Firefox: hide scrollbar
          msOverflowStyle: 'none',  // IE/Edge: hide scrollbar
        }}
      >
        {/* spacer: lets the first lyric line scroll to center */}
        <div style={{ height: '30vh' }} />

        {segments.map((seg, idx) => {
          const isActive = idx === activeIdx
          const isPast   = idx < activeIdx

          return (
            <div
              key={seg.id ?? idx}
              ref={isActive ? activeRef : null}
              style={{ marginBottom: '1.4rem' }}
            >
              {displayMode === 'both' ? (
                <div>
                  {/* Original lyric line */}
                  <p style={{
                    fontSize:   '1.45rem',
                    fontWeight: isActive ? 700 : 400,
                    color:      isActive ? '#ffffff' : isPast ? '#374151' : '#6b7280',
                    lineHeight: 1.3,
                    transition: 'color 0.3s ease, font-weight 0.2s ease',
                    marginBottom: '0.2rem',
                  }}>
                    {seg.original}
                  </p>
                  {/* English translation — slightly smaller */}
                  <p style={{
                    fontSize:   '1rem',
                    fontWeight: isActive ? 600 : 400,
                    color:      isActive ? '#c4b5fd' : isPast ? '#1f2937' : '#374151',
                    lineHeight: 1.4,
                    transition: 'color 0.3s ease',
                  }}>
                    {seg.translated}
                  </p>
                </div>
              ) : (
                /* Single mode — original or translated only */
                <p style={{
                  fontSize:   '1.6rem',
                  fontWeight: isActive ? 700 : 400,
                  color:      isActive ? '#ffffff' : isPast ? '#374151' : '#6b7280',
                  lineHeight: 1.3,
                  transition: 'color 0.3s ease, font-weight 0.2s ease',
                }}>
                  {displayMode === 'original' ? seg.original : seg.translated}
                </p>
              )}
            </div>
          )
        })}

        {/* spacer: lets the last lyric line scroll to center */}
        <div style={{ height: '30vh' }} />
      </div>

      {/* hide scrollbar in WebKit/Chrome */}
      <style>{`
        div::-webkit-scrollbar { display: none; }
      `}</style>
    </div>
  )
}
