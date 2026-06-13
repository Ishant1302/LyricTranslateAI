/**
 * api.js — Centralised Axios helpers for the LyricTranslate AI backend.
 *
 * The Vite dev-server proxies /api → http://localhost:8000 so we don't
 * need to hard-code the backend URL in dev mode.
 */

import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 30_000, // 30 s — uploads can take a while
})

// ── Endpoints ──────────────────────────────────────────────────────────────

/**
 * Upload an audio file (File object) and start the processing pipeline.
 * @param {File}   file    - Audio file (MP3, WAV, …)
 * @param {string} title   - Optional song title
 * @param {string} artist  - Optional artist name
 * @param {Function} onProgress - Upload progress callback (0-100)
 * @returns {Promise<{job_id: string}>}
 */
export async function uploadFile(file, title = '', artist = '', onProgress = null) {
  const form = new FormData()
  form.append('file', file)
  if (title)  form.append('title', title)
  if (artist) form.append('artist', artist)

  const response = await api.post('/upload', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress: onProgress
      ? (e) => onProgress(Math.round((e.loaded * 100) / (e.total || 1)))
      : undefined,
    timeout: 120_000, // 2-minute timeout for large files
  })
  return response.data
}

/**
 * Submit a song URL (YouTube, SoundCloud, etc.) for processing.
 * @param {string} url    - Public song URL
 * @param {string} title  - Optional title
 * @param {string} artist - Optional artist
 * @returns {Promise<{job_id: string}>}
 */
export async function uploadUrl(url, title = '', artist = '') {
  const form = new FormData()
  form.append('url', url)
  if (title)  form.append('title', title)
  if (artist) form.append('artist', artist)

  const response = await api.post('/upload', form, {
    timeout: 300_000, // 5-minute timeout — YouTube downloads can be slow
  })
  return response.data
}

/**
 * Poll the backend for job progress.
 * @param {string} jobId
 * @returns {Promise<{status, progress, step, error, result}>}
 */
export async function getStatus(jobId) {
  const response = await api.get(`/status/${jobId}`)
  return response.data
}

/**
 * Stream URL for the uploaded audio file.
 * @param {string} jobId
 * @returns {string} URL
 */
export function getAudioUrl(jobId) {
  return `/api/audio/${jobId}`
}
