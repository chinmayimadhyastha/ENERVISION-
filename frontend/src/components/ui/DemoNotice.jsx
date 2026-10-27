import { Info } from 'lucide-react'
import { cx } from '../../utils/format.js'
import { isLiveBackend } from '../../utils/env.js'

/**
 * Canonical wording for placeholder data so it can never be confused with
 * final research results. Defined once and reused across pages.
 */
export const RESEARCH_DEMO_LABEL = 'DEMO / ILLUSTRATIVE DATA — NOT FINAL RESEARCH RESULTS'
export const ASSET_DEMO_LABEL = 'DEMO ASSET · ILLUSTRATIVE METADATA'

/**
 * Consistent "this is placeholder data" banner.
 *
 * By default it renders only in DEMO MODE. In LIVE MODE the UI shows backend
 * data (or an error state), so the demo claim is hidden — pass `showInLive` to
 * force it. Options are limited to the label, tone and body text.
 */
export default function DemoNotice({ label = 'DEMO / PLACEHOLDER', children, className = '', tone = 'amber', showInLive = false }) {
  if (!showInLive && isLiveBackend()) return null

  const tones = {
    amber: 'border-solar-400/25 bg-solar-400/[0.06] text-solar-200',
    sky: 'border-sky-400/25 bg-sky-400/[0.06] text-sky-200',
    brand: 'border-brand-400/25 bg-brand-400/[0.06] text-brand-200',
    slate: 'border-graphite-650 bg-graphite-900/60 text-graphite-200',
  }
  return (
    <div className={cx('flex items-start gap-3 rounded-lg border px-3.5 py-2.5', tones[tone] || tones.amber, className)}>
      <Info className="mt-0.5 h-4 w-4 shrink-0 opacity-80" />
      <div className="min-w-0 flex-1 text-xs leading-relaxed">
        <span className="mr-2 inline-block max-w-full break-words rounded border border-current/20 bg-black/20 px-1.5 py-0.5 align-middle font-mono text-[10px] font-bold uppercase tracking-wide">
          {label}
        </span>
        {children}
      </div>
    </div>
  )
}
