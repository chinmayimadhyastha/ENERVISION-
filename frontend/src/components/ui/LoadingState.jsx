import { Loader2 } from 'lucide-react'
import { cx } from '../../utils/format.js'

/** Skeleton block used by loading states. */
export function Skeleton({ className = '' }) {
  return <div className={cx('ev-shimmer rounded-md bg-graphite-800', className)} />
}

/** Card-shaped loading placeholder. */
export function CardSkeleton({ lines = 3, className = '' }) {
  return (
    <div className={cx('panel p-5', className)}>
      <Skeleton className="h-4 w-32" />
      <div className="mt-4 space-y-3">
        {Array.from({ length: lines }).map((_, i) => (
          <Skeleton key={i} className={cx('h-3', i % 3 === 0 ? 'w-full' : i % 3 === 1 ? 'w-5/6' : 'w-3/4')} />
        ))}
      </div>
    </div>
  )
}

/**
 * Generic page-level loading state.
 * variant: 'cards' | 'chart' | 'table' | 'page'
 */
export default function LoadingState({ label = 'Loading…', variant = 'page', rows = 3, className = '' }) {
  if (variant === 'cards') {
    return (
      <div className={cx('grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4', className)}>
        {Array.from({ length: 4 }).map((_, i) => (
          <CardSkeleton key={i} lines={2} />
        ))}
      </div>
    )
  }

  if (variant === 'chart') {
    return (
      <div className={cx('panel p-5', className)}>
        <Skeleton className="h-4 w-40" />
        <Skeleton className="mt-5 h-[260px] w-full" />
      </div>
    )
  }

  if (variant === 'table') {
    return (
      <div className={cx('panel p-5', className)}>
        <Skeleton className="h-4 w-40" />
        <div className="mt-5 space-y-2.5">
          {Array.from({ length: rows + 3 }).map((_, i) => (
            <Skeleton key={i} className="h-8 w-full" />
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className={cx('flex flex-col items-center justify-center gap-3 py-16', className)} role="status">
      <span className="relative flex h-11 w-11 items-center justify-center">
        <span className="absolute inset-0 rounded-full border border-brand-400/20" />
        <span className="absolute inset-0 animate-ping-ring rounded-full border border-brand-400/40" />
        <Loader2 className="h-5 w-5 animate-spin text-brand-300" />
      </span>
      <p className="eyebrow">{label}</p>
    </div>
  )
}
