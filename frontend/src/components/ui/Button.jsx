import { forwardRef } from 'react'
import { cx } from '../../utils/format.js'

const VARIANTS = {
  primary:
    'bg-emerald-700 text-white shadow-sm hover:bg-emerald-600 focus-visible:ring-emerald-500/50 active:bg-emerald-800 keep-white',
  secondary:
    'bg-white text-slate-700 border border-slate-300 hover:bg-slate-50 hover:text-slate-900 focus-visible:ring-emerald-500/30 shadow-sm',
  ghost: 'text-slate-600 hover:bg-slate-100 hover:text-slate-900 focus-visible:ring-emerald-500/30',
  outline:
    'bg-transparent text-emerald-800 border border-emerald-700/40 hover:bg-emerald-50 focus-visible:ring-emerald-500/40',
  solar:
    'bg-amber-500 text-slate-950 shadow-sm hover:bg-amber-400 focus-visible:ring-amber-400/50 font-semibold',
  danger: 'bg-rose-600 text-white hover:bg-rose-500 focus-visible:ring-rose-400/50 keep-white',
  dark: 'bg-slate-900 text-white hover:bg-slate-800 keep-white',
}

const SIZES = {
  sm: 'h-8 px-3 text-xs gap-1.5',
  md: 'h-9 px-3.5 text-[13px] gap-2',
  lg: 'h-11 px-5 text-sm gap-2',
  icon: 'h-9 w-9 justify-center',
}

const Button = forwardRef(function Button(
  { variant = 'secondary', size = 'md', className = '', as: As = 'button', children, ...rest },
  ref,
) {
  return (
    <As
      ref={ref}
      className={cx(
        'inline-flex select-none items-center justify-center rounded-lg font-semibold tracking-tight',
        'outline-none transition-all duration-150 ease-in-out focus-visible:ring-2',
        'disabled:pointer-events-none disabled:opacity-50',
        VARIANTS[variant] || VARIANTS.secondary,
        SIZES[size] || SIZES.md,
        className,
      )}
      {...rest}
    >
      {children}
    </As>
  )
})

export default Button
