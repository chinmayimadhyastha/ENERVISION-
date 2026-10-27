import { ChevronRight } from 'lucide-react'
import { Link } from 'react-router-dom'
import { cx } from '../../utils/format.js'
import Badge from './Badge.jsx'

/**
 * Standard page header used by every route: breadcrumb, title, description,
 * right-aligned actions and an optional monospace meta strip.
 */
export default function PageHeader({
  eyebrow,
  breadcrumb = [],
  title,
  description,
  badge,
  actions,
  meta,
  icon,
  className = '',
}) {
  return (
    <header className={cx('relative animate-fade-up', className)}>
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <nav className="flex flex-wrap items-center gap-1 font-mono text-[10px] font-semibold uppercase tracking-[0.14em] text-graphite-500">
            {eyebrow ? <span className="text-brand-300/80">{eyebrow}</span> : null}
            {eyebrow && breadcrumb.length ? (
              <ChevronRight className="h-3 w-3 text-graphite-600" />
            ) : null}
            {breadcrumb.map((b, i) => (
              <span key={`${b.label}-${i}`} className="inline-flex items-center gap-1">
                {i > 0 ? <ChevronRight className="h-3 w-3 text-graphite-600" /> : null}
                {b.to ? (
                  <Link to={b.to} className="transition-colors hover:text-graphite-200">
                    {b.label}
                  </Link>
                ) : (
                  <span className="text-graphite-400">{b.label}</span>
                )}
              </span>
            ))}
          </nav>

          <div className="mt-2.5 flex items-start gap-3">
            {icon ? (
              <span className="mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-graphite-700 bg-graphite-900/80 text-brand-300">
                {icon}
              </span>
            ) : null}
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2.5">
                <h1 className="font-display text-[22px] font-bold leading-tight tracking-tight text-white sm:text-2xl">
                  {title}
                </h1>
                {badge}
              </div>
              {description ? (
                <p className="mt-1.5 max-w-3xl text-[13px] leading-relaxed text-graphite-400">{description}</p>
              ) : null}
            </div>
          </div>
        </div>

        {actions ? <div className="flex flex-wrap items-center gap-2 lg:pt-1">{actions}</div> : null}
      </div>

      {meta?.length ? (
        <div className="mt-4 flex flex-wrap items-center gap-x-5 gap-y-2 rounded-lg border border-graphite-700/70 bg-graphite-900/50 px-3.5 py-2.5">
          {meta.map((m, i) => (
            <div key={`${m.label}-${i}`} className="flex items-center gap-2">
              <span className="eyebrow">{m.label}</span>
              <span className="font-mono text-[11px] font-semibold text-graphite-100">{m.value}</span>
              {i < meta.length - 1 ? <span className="ml-3 hidden h-3 w-px bg-graphite-700 sm:block" /> : null}
            </div>
          ))}
        </div>
      ) : null}
    </header>
  )
}
