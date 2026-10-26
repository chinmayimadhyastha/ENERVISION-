import { cx } from '../../utils/format.js'

const ACCENTS = {
  brand: 'before:bg-brand-400',
  solar: 'before:bg-solar-400',
  wind: 'before:bg-wind-400',
  violet: 'before:bg-violet-400',
  none: '',
}

/**
 * Dark control-room surface. Optional top accent hairline via `accent`.
 */
export default function Card({
  className = '',
  padded = false,
  hover = false,
  accent = 'none',
  glow = false,
  children,
  ...rest
}) {
  return (
    <div
      className={cx(
        'panel',
        accent !== 'none' &&
          cx(
            'before:absolute before:inset-x-0 before:top-0 before:h-px before:rounded-t-xl before:content-[""]',
            ACCENTS[accent] || ACCENTS.brand,
          ),
        padded && 'p-4 sm:p-5',
        hover && 'panel-interactive hover:-translate-y-0.5',
        glow && accent === 'solar' && 'hover:shadow-glow-solar',
        glow && accent === 'wind' && 'hover:shadow-glow-wind',
        glow && (accent === 'brand' || accent === 'none') && 'hover:shadow-glow-brand',
        'overflow-hidden',
        className,
      )}
      {...rest}
    >
      {children}
    </div>
  )
}

const ICON_TONES = {
  brand: 'bg-brand-400/10 text-brand-300 ring-brand-400/20',
  solar: 'bg-solar-400/10 text-solar-300 ring-solar-400/20',
  wind: 'bg-wind-400/10 text-wind-300 ring-wind-400/20',
  violet: 'bg-violet-400/10 text-violet-300 ring-violet-400/20',
  neutral: 'bg-white/5 text-graphite-300 ring-white/10',
}

export function CardHeader({ title, subtitle, icon, tone = 'brand', actions, className = '' }) {
  return (
    <div className={cx('flex items-start justify-between gap-3', className)}>
      <div className="flex min-w-0 items-start gap-3">
        {icon ? (
          <span
            className={cx(
              'mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg ring-1 ring-inset',
              ICON_TONES[tone] || ICON_TONES.brand,
            )}
          >
            {icon}
          </span>
        ) : null}
        <div className="min-w-0">
          <h3 className="truncate font-display text-[15px] font-semibold tracking-tight text-white">
            {title}
          </h3>
          {subtitle ? (
            <p className="mt-0.5 text-xs leading-relaxed text-graphite-400">{subtitle}</p>
          ) : null}
        </div>
      </div>
      {actions ? <div className="flex shrink-0 items-center gap-2">{actions}</div> : null}
    </div>
  )
}
