import { AlertTriangle, RefreshCw } from 'lucide-react'
import { cx } from '../../utils/format.js'
import Button from './Button.jsx'

export default function ErrorState({
  title = 'Something went wrong',
  message,
  onRetry,
  className = '',
  compact = false,
}) {
  return (
    <div
      className={cx(
        'flex flex-col items-center justify-center rounded-xl border border-rose-500/25 bg-rose-500/5 px-6 text-center',
        compact ? 'py-8' : 'py-12',
        className,
      )}
      role="alert"
    >
      <span className="flex h-12 w-12 items-center justify-center rounded-xl border border-rose-500/25 bg-graphite-900/80 text-rose-300">
        <AlertTriangle className="h-6 w-6" />
      </span>
      <h3 className="mt-3 font-display text-sm font-bold text-rose-200">{title}</h3>
      <p className="mt-1 max-w-md text-xs leading-relaxed text-graphite-400">
        {message || 'The data could not be loaded. Check that the ENERVISION API is reachable, then retry.'}
      </p>
      {onRetry ? (
        <Button variant="secondary" size="sm" className="mt-4" onClick={onRetry}>
          <RefreshCw className="h-3.5 w-3.5" />
          Retry
        </Button>
      ) : null}
    </div>
  )
}
