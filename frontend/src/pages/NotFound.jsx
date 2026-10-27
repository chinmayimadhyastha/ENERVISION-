import { Link } from 'react-router-dom'
import { ArrowRight, Compass, Factory, LayoutDashboard } from 'lucide-react'

import Button from '../components/ui/Button.jsx'

export default function NotFound() {
  return (
    <div className="relative flex min-h-[70vh] flex-col items-center justify-center overflow-hidden px-4 py-16 text-center">
      <div className="pointer-events-none absolute inset-0 ev-grid opacity-[0.12]" aria-hidden />
      <div className="pointer-events-none absolute left-1/2 top-1/3 h-72 w-72 -translate-x-1/2 -translate-y-1/2 rounded-full bg-brand-500/10 blur-3xl" aria-hidden />

      {/* Radar / scan motif */}
      <div className="relative flex h-56 w-56 items-center justify-center sm:h-64 sm:w-64">
        <div className="absolute inset-0 rounded-full border border-graphite-700/70" aria-hidden />
        <div className="absolute inset-7 rounded-full border border-graphite-700/60" aria-hidden />
        <div className="absolute inset-14 rounded-full border border-graphite-700/50" aria-hidden />
        <div className="absolute inset-0 rounded-full ev-contour opacity-70" aria-hidden />

        {/* Rotating sweep */}
        <div
          className="absolute inset-0 animate-sweep rounded-full"
          style={{
            background:
              'conic-gradient(from 0deg, rgba(45,212,191,0.35) 0deg, rgba(45,212,191,0.06) 55deg, transparent 90deg, transparent 360deg)',
          }}
          aria-hidden
        />

        {/* Crosshair */}
        <div className="absolute left-1/2 top-3 h-[calc(100%-1.5rem)] w-px -translate-x-1/2 bg-graphite-700/40" aria-hidden />
        <div className="absolute top-1/2 left-3 h-px w-[calc(100%-1.5rem)] -translate-y-1/2 bg-graphite-700/40" aria-hidden />

        {/* Pulsing node */}
        <span className="absolute left-1/2 top-8 h-2 w-2 -translate-x-1/2 rounded-full bg-brand-400 shadow-[0_0_12px_rgba(45,212,191,0.9)]" aria-hidden />
        <span className="absolute left-1/2 top-8 h-2 w-2 -translate-x-1/2 animate-ping-ring rounded-full bg-brand-400" aria-hidden />

        {/* 404 readout */}
        <div className="relative z-10 flex flex-col items-center">
          <span className="font-mono text-[10px] font-bold uppercase tracking-[0.28em] text-brand-300/80">Signal lost</span>
          <span className="font-display text-6xl font-extrabold leading-none tracking-tight text-white sm:text-7xl">404</span>
        </div>
      </div>

      <p className="mt-8 font-mono text-[11px] font-bold uppercase tracking-[0.2em] text-brand-300">Error 404</p>
      <h1 className="mt-2 font-display text-2xl font-extrabold tracking-tight text-white sm:text-3xl">
        This coordinate isn&rsquo;t on the grid
      </h1>
      <p className="mt-2 max-w-md text-sm leading-relaxed text-graphite-400">
        The page you requested does not exist in the ENERVISION frontend. Use the navigation or return to the dashboard.
      </p>

      <div className="mt-6 flex flex-wrap items-center justify-center gap-3">
        <Button as={Link} to="/" variant="primary">
          <LayoutDashboard className="h-4 w-4" />
          Back to Dashboard
        </Button>
        <Button as={Link} to="/plants" variant="secondary">
          <Factory className="h-4 w-4" />
          Plant Explorer
        </Button>
      </div>

      <div className="mt-8 inline-flex items-center gap-2 rounded-full border border-graphite-700/70 bg-graphite-900/60 px-3 py-1.5 text-[11px] text-graphite-500">
        <Compass className="h-3.5 w-3.5 text-graphite-400" />
        Try the Dashboard, Plants, Forecast or Model Performance views
        <ArrowRight className="h-3 w-3" />
      </div>
    </div>
  )
}
