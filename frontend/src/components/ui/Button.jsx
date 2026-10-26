import { forwardRef } from 'react'
import { cx } from '../../utils/format.js'

const VARIANTS = {
  primary:
    'bg-brand-500 text-graphite-950 shadow-[0_6px_24px_-10px_rgba(20,184,166,0.85)] hover:bg-brand-400 focus-visible:ring-brand-400/50 active:bg-brand-600',
  secondary:
    'bg-graphite-800 text-graphite-100 ring-1 ring-inset ring-white/10 hover:bg-graphite-750 hover:ring-white/20 focus-visible:ring-brand-400/40',
  ghost: 'text-graphite-300 hover:bg-white/5 hover:text-white focus-visible:ring-brand-400/30',
  outline:
    'bg-transparent text-brand-300 ring-1 ring-inset ring-brand-400/30 hover:bg-brand-400/10 focus-visible:ring-brand-400/50',
  solar:
    'bg-solar-400 text-graphite-950 shadow-[0_6px_24px_-10px_rgba(245,158,11,0.85)] hover:bg-solar-300 focus-visible:ring-solar-400/50',
  danger: 'bg-rose-500 text-white hover:bg-rose-400 focus-visible:ring-rose-400/50',
  dark: 'bg-graphite-950 text-white ring-1 ring-inset ring-white/10 hover:bg-black focus-visible:ring-white/20',
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
        'outline-none transition-all duration-200 ease-smooth focus-visible:ring-2',
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
