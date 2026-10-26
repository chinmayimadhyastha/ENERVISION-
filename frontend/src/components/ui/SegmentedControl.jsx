import { cx } from '../../utils/format.js'

/**
 * Segmented control (forecast horizon, analytics period, chart tabs).
 * options: [{ value, label, icon? }]
 */
export default function SegmentedControl({ options = [], value, onChange, size = 'md', className = '', ariaLabel }) {
  const pad = size === 'sm' ? 'px-2.5 py-1 text-[11px]' : 'px-3 py-1.5 text-xs'
  return (
    <div
      role="tablist"
      aria-label={ariaLabel}
      className={cx(
        'inline-flex items-center gap-1 rounded-lg border border-graphite-700/80 bg-graphite-900/70 p-1',
        className,
      )}
    >
      {options.map((o) => {
        const active = String(o.value) === String(value)
        return (
          <button
            key={o.value}
            type="button"
            role="tab"
            aria-selected={active}
            onClick={() => onChange?.(o.value)}
            className={cx(
              'inline-flex items-center gap-1.5 rounded-md font-semibold transition-all duration-200 ease-smooth',
              pad,
              active
                ? 'bg-brand-400/15 text-brand-200 ring-1 ring-inset ring-brand-400/30'
                : 'text-graphite-400 hover:bg-white/5 hover:text-graphite-100',
            )}
          >
            {o.icon ? <span className="shrink-0">{o.icon}</span> : null}
            {o.label}
          </button>
        )
      })}
    </div>
  )
}
