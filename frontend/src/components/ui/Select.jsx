import { ChevronDown } from 'lucide-react'
import { cx } from '../../utils/format.js'

/** Accessible, styled native select with optional inline label / leading icon. */
export default function Select({
  label,
  hint,
  icon,
  className = '',
  selectClassName = '',
  options = [],
  children,
  ...rest
}) {
  return (
    <label className={cx('block', className)}>
      {label ? <span className="eyebrow mb-1.5 block">{label}</span> : null}
      <span className="relative block">
        {icon ? (
          <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-graphite-400">{icon}</span>
        ) : null}
        <select
          className={cx(
            'w-full appearance-none rounded-lg border border-graphite-650 bg-graphite-900/80 py-2 pr-9 text-[13px] font-medium text-graphite-100',
            'outline-none transition focus:border-brand-500/70 focus:ring-2 focus:ring-brand-500/20',
            icon ? 'pl-9' : 'pl-3',
            selectClassName,
          )}
          {...rest}
        >
          {options.length
            ? options.map((o) => (
                <option key={o.value} value={o.value} className="bg-graphite-900 text-graphite-100">
                  {o.label}
                </option>
              ))
            : children}
        </select>
        <ChevronDown className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-graphite-400" />
      </span>
      {hint ? <span className="mt-1 block text-[11px] text-graphite-400">{hint}</span> : null}
    </label>
  )
}
