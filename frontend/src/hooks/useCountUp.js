import { useEffect, useRef, useState } from 'react'

const prefersReducedMotion = () =>
  typeof window !== 'undefined' &&
  window.matchMedia &&
  window.matchMedia('(prefers-reduced-motion: reduce)').matches

/**
 * Animates a numeric value toward `target` using requestAnimationFrame with a
 * cubic ease-out. Starts from the previous value so updates feel continuous.
 * Respects prefers-reduced-motion and cleans up on unmount.
 */
export function useCountUp(target, { duration = 900, decimals = 0, start = 0, enabled = true } = {}) {
  const to = Number(target)
  const finite = Number.isFinite(to)
  const [value, setValue] = useState(() =>
    finite ? (enabled && !prefersReducedMotion() ? start : to) : 0,
  )
  const fromRef = useRef(finite ? start : 0)
  const rafRef = useRef(0)

  useEffect(() => {
    if (!finite) return undefined
    if (!enabled || prefersReducedMotion()) {
      fromRef.current = to
      setValue(to)
      return undefined
    }
    const from = fromRef.current
    const delta = to - from
    if (Math.abs(delta) < 1e-9) {
      fromRef.current = to
      return undefined
    }
    let startTime = 0
    const ease = (t) => 1 - Math.pow(1 - t, 3)
    const step = (ts) => {
      if (!startTime) startTime = ts
      const p = Math.min(1, (ts - startTime) / duration)
      setValue(from + delta * ease(p))
      if (p < 1) {
        rafRef.current = requestAnimationFrame(step)
      } else {
        fromRef.current = to
      }
    }
    rafRef.current = requestAnimationFrame(step)
    return () => cancelAnimationFrame(rafRef.current)
  }, [to, duration, enabled, finite])

  if (!finite) return target
  return decimals ? Number(value.toFixed(decimals)) : Math.round(value)
}

/** Fires once when the element scrolls into view (IntersectionObserver). */
export function useInView({ rootMargin = '0px 0px -8% 0px', threshold = 0.12, once = true } = {}) {
  const ref = useRef(null)
  const [inView, setInView] = useState(false)

  useEffect(() => {
    const el = ref.current
    if (!el || typeof IntersectionObserver === 'undefined') {
      setInView(true)
      return undefined
    }
    const obs = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setInView(true)
          if (once) obs.disconnect()
        } else if (!once) {
          setInView(false)
        }
      },
      { rootMargin, threshold },
    )
    obs.observe(el)
    return () => obs.disconnect()
  }, [rootMargin, threshold, once])

  return [ref, inView]
}
