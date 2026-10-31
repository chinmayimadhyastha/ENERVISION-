import { useState } from 'react'

/**
 * Dedicated, official Karnataka Government asset slot.
 *
 * Tries to load `/assets/karnataka-gov-logo.png`.
 * If missing or fails to load, gracefully falls back to a neutral administrative badge
 * placeholder without inventing or fabricating state insignia.
 */
export default function GovEmblem({ className = 'h-10 w-10' }) {
  const [loadError, setLoadError] = useState(false)

  if (!loadError) {
    return (
      <img
        src="/assets/karnataka-gov-logo.png"
        alt="Government of Karnataka Emblem"
        onError={() => setLoadError(true)}
        className={`${className} object-contain`}
      />
    )
  }

  // Neutral public-sector administration badge fallback
  return (
    <div
      className={`${className} flex items-center justify-center rounded-lg border border-emerald-700/30 bg-emerald-50 text-emerald-800 shadow-sm`}
      title="Government of Karnataka Emblem (Slot: /assets/karnataka-gov-logo.png)"
    >
      <svg viewBox="0 0 36 36" className="h-7 w-7 text-emerald-800" fill="none" stroke="currentColor">
        <circle cx="18" cy="18" r="15" strokeWidth="1.75" />
        <circle cx="18" cy="18" r="11" strokeWidth="0.75" strokeDasharray="2 2" />
        <path d="M18 10v16M10 18h16" strokeWidth="1" strokeOpacity="0.5" />
        <circle cx="18" cy="18" r="3" fill="currentColor" fillOpacity="0.2" />
        <text
          x="18"
          y="20.5"
          textAnchor="middle"
          fontSize="7"
          fontWeight="700"
          fontFamily="system-ui"
          fill="currentColor"
          stroke="none"
        >
          KA
        </text>
      </svg>
    </div>
  )
}
