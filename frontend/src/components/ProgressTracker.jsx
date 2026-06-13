/**
 * ProgressTracker.jsx — Visual step-by-step processing pipeline indicator.
 *
 * Shows the 5 pipeline stages:
 *   Uploading → Isolating Vocals → Transcribing → Translating → Ready
 *
 * Each step shows as complete ✓, active (animated), or pending (grey).
 */

import { Check, Loader2 } from 'lucide-react'

const STEPS = [
  { label: 'Uploading',        key: 'Uploading',         icon: '📤' },
  { label: 'Isolating Vocals', key: 'Isolating Vocals',  icon: '🎵' },
  { label: 'Transcribing',     key: 'Transcribing',      icon: '🎙️' },
  { label: 'Translating',      key: 'Translating',       icon: '🤖' },
  { label: 'Ready',            key: 'Ready',             icon: '✨' },
]

/**
 * Determine which step is active and which are complete.
 */
function resolveStepStates(currentStep, status) {
  const activeIdx = STEPS.findIndex((s) => currentStep?.includes(s.key))
  if (status === 'complete') {
    return STEPS.map(() => 'complete')
  }
  return STEPS.map((_, i) => {
    if (i < activeIdx)  return 'complete'
    if (i === activeIdx) return 'active'
    return 'pending'
  })
}

export default function ProgressTracker({ step, progress, status, error }) {
  const states = resolveStepStates(step, status)

  return (
    <div className="glass p-7 animate-slide-up">
      <div className="flex items-center justify-between mb-5">
        <h3 className="font-semibold text-white">Processing</h3>
        {status !== 'error' && (
          <span className="text-sm font-medium text-brand-300">{progress ?? 0}%</span>
        )}
      </div>

      {/* Overall progress bar */}
      {status !== 'error' && (
        <div className="h-2 bg-surface-700 rounded-full overflow-hidden mb-7">
          <div
            className="h-full rounded-full transition-all duration-700 ease-out"
            style={{
              width: `${progress || 0}%`,
              background: 'linear-gradient(90deg, #5355e5, #8195f7, #a78bfa)',
            }}
          />
        </div>
      )}

      {/* Step indicators */}
      <div className="flex items-start gap-2">
        {STEPS.map((s, i) => {
          const state = states[i]
          return (
            <div key={s.key} className="flex-1 flex flex-col items-center gap-2">
              {/* Circle */}
              <div
                className={`w-9 h-9 rounded-full flex items-center justify-center text-sm font-semibold transition-all duration-500
                  ${state === 'complete' ? 'step-complete' : ''}
                  ${state === 'active'   ? 'step-active'   : ''}
                  ${state === 'pending'  ? 'step-pending'  : ''}`}
              >
                {state === 'complete' ? (
                  <Check className="w-4 h-4" />
                ) : state === 'active' ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <span className="text-xs">{i + 1}</span>
                )}
              </div>

              {/* Connector line (not after last step) */}
              {i < STEPS.length - 1 && (
                <div className="absolute" />
              )}

              {/* Label */}
              <span
                className={`text-[10px] font-medium text-center leading-tight transition-colors duration-300
                  ${state === 'complete' ? 'text-brand-300' : ''}
                  ${state === 'active'   ? 'text-white'     : ''}
                  ${state === 'pending'  ? 'text-gray-600'  : ''}`}
              >
                {s.icon} {s.label}
              </span>
            </div>
          )
        })}
      </div>

      {/* Current step label */}
      {status === 'processing' && step && (
        <p className="mt-5 text-center text-sm text-gray-400 animate-pulse">
          {step}…
        </p>
      )}

      {/* Error state */}
      {status === 'error' && error && (
        <div className="mt-5 p-4 bg-red-900/20 border border-red-500/30 rounded-xl">
          <p className="text-sm text-red-400 font-medium">⚠️ Processing Failed</p>
          <p className="text-xs text-red-300/70 mt-1 break-words">{error}</p>
        </div>
      )}

      {/* Complete state */}
      {status === 'complete' && (
        <p className="mt-5 text-center text-sm text-brand-300 font-medium">
          ✨ Lyrics ready — press play!
        </p>
      )}
    </div>
  )
}
