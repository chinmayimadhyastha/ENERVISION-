import { Sparkles } from 'lucide-react'
import { Link } from 'react-router-dom'
import { cx } from '../../utils/format.js'
import Badge from '../ui/Badge.jsx'

/**
 * Deterministic insight panel built from the observed daily dataset. It does not
 * contain model-generated text or fabricated peaks; every bullet is derived from
 * backend aggregates.
 */
export default function InsightPanel({ insight, className = '', title = 'Dataset Insight' }) {
  if (!insight) return null
  const { headline, bullets = [], disclaimer, dominantSource, dominantShare, peakWindow, peakForecastMW } = insight

  return (
    <div
      className={cx(
        'relative overflow-hidden rounded-xl border border-brand-400/20 bg-graphite-900 p-5 shadow-panel sm:p-6',
        className,
      )}
    >
      <div className="pointer-events-none absolute inset-0 ev-grid opacity-40" aria-hidden />
      <div className="pointer-events-none absolute -right-16 -top-16 h-48 w-48 rounded-full bg-brand-400/15 blur-3xl" aria-hidden />
      <div className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-brand-400/50 to-transparent" aria-hidden />

      <div className="relative">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg border border-brand-400/30 bg-brand-400/10 text-brand-300">
              <Sparkles className="h-4 w-4" />
            </span>
            <div>
              <h3 className="font-display text-sm font-bold text-white">{title}</h3>
              <p className="eyebrow">Derived from observed daily data</p>
            </div>
          </div>
          <Badge tone="brand" size="sm" dot>
            API-derived
          </Badge>
        </div>

        {headline ? <p className="mt-4 text-[15px] font-semibold leading-relaxed text-graphite-100">{headline}</p> : null}

        {bullets.length ? (
          <ul className="mt-4 space-y-2.5">
            {bullets.map((b, i) => (
              <li key={i} className="flex gap-2.5 text-xs leading-relaxed text-graphite-300">
                <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-brand-400" />
                <span>{b}</span>
              </li>
            ))}
          </ul>
        ) : null}

        <div className="mt-4 flex flex-wrap items-center gap-x-5 gap-y-2 border-t border-graphite-700/70 pt-3">
          {dominantSource ? (
            <span className="flex items-center gap-2">
              <span className="eyebrow">Dominant source</span>
              <span className="font-mono text-[11px] font-semibold text-graphite-100">
                {dominantSource}
                {dominantShare !== null && dominantShare !== undefined ? ` · ${dominantShare}%` : ''}
              </span>
            </span>
          ) : null}
          {peakWindow ? (
            <span className="flex items-center gap-2">
              <span className="eyebrow">Peak window</span>
              <span className="font-mono text-[11px] font-semibold text-graphite-100">{peakWindow}</span>
            </span>
          ) : null}
          {peakForecastMW != null ? (
            <span className="flex items-center gap-2">
              <span className="eyebrow">Peak output</span>
              <span className="font-mono text-[11px] font-semibold text-graphite-100">{peakForecastMW} MW</span>
            </span>
          ) : null}
        </div>

        {disclaimer ? (
          <p className="mt-3 text-[11px] leading-relaxed text-graphite-500">{disclaimer}</p>
        ) : null}
      </div>
    </div>
  )
}
