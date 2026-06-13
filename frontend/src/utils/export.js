/**
 * export.js — Helper utilities to export lyrics as SRT, TXT, or copy to clipboard.
 */

/**
 * Convert seconds (float) to SRT timestamp format: HH:MM:SS,mmm
 */
function toSrtTime(seconds) {
  const ms  = Math.round((seconds % 1) * 1000)
  const s   = Math.floor(seconds) % 60
  const m   = Math.floor(seconds / 60) % 60
  const h   = Math.floor(seconds / 3600)
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')},${String(ms).padStart(3, '0')}`
}

/**
 * Download the lyrics as an SRT subtitle file.
 * @param {Array}  segments - Array of lyric segment objects
 * @param {string} mode     - 'original' | 'translated' | 'both'
 * @param {string} filename - Base filename (without extension)
 */
export function downloadSRT(segments, mode = 'translated', filename = 'lyrics') {
  const lines = segments.map((seg, idx) => {
    const start = toSrtTime(seg.time)
    const end   = toSrtTime(seg.time + seg.duration)

    let text = ''
    if (mode === 'both') {
      text = `${seg.original}\n${seg.translated}`
    } else if (mode === 'translated') {
      text = seg.translated
    } else {
      text = seg.original
    }

    return `${idx + 1}\n${start} --> ${end}\n${text}`
  })

  _downloadBlob(lines.join('\n\n') + '\n', `${filename}.srt`, 'text/plain;charset=utf-8')
}

/**
 * Download the lyrics as a plain-text file with original + translation columns.
 * @param {Array}  segments
 * @param {object} metadata - {title, artist}
 * @param {string} filename
 */
export function downloadTXT(segments, metadata = {}, filename = 'lyrics') {
  const header = [
    `🎵 ${metadata.title || 'Unknown'} — ${metadata.artist || 'Unknown'}`,
    '─'.repeat(60),
    `${'Time'.padEnd(10)} ${'Original'.padEnd(35)} Translation`,
    '─'.repeat(60),
  ].join('\n')

  const rows = segments.map((seg) => {
    const time = `[${toSrtTime(seg.time).slice(0, 8)}]`
    return `${time.padEnd(10)} ${seg.original.padEnd(35)} ${seg.translated}`
  })

  _downloadBlob([header, ...rows].join('\n'), `${filename}.txt`, 'text/plain;charset=utf-8')
}

/**
 * Copy a single lyric line to the clipboard.
 * @param {object} segment
 * @param {string} mode - 'original' | 'translated' | 'both'
 */
export async function copyLine(segment, mode = 'both') {
  let text = ''
  if (mode === 'both')       text = `${segment.original} | ${segment.translated}`
  else if (mode === 'translated') text = segment.translated
  else                            text = segment.original

  await navigator.clipboard.writeText(text)
}

/** Internal: trigger a browser file download. */
function _downloadBlob(content, filename, mimeType) {
  const blob = new Blob([content], { type: mimeType })
  const url  = URL.createObjectURL(blob)
  const a    = document.createElement('a')
  a.href     = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}
