import { useEffect, useState } from 'react'
import { Outlet, useLocation } from 'react-router-dom'
import Header from './Header.jsx'
import Sidebar from './Sidebar.jsx'
import { API_MODE } from '../../services/api.js'

function Footer() {
  return (
    <footer className="mt-12 border-t border-slate-200 bg-white px-4 py-8 text-xs text-slate-500 sm:px-6 lg:px-8">
      <div className="mx-auto flex max-w-[1500px] flex-col items-start justify-between gap-4 md:flex-row md:items-center">
        <div>
          <p className="font-semibold text-slate-800">
            Government of Karnataka · Department of Energy & Karnataka Renewable Energy Development Ltd (KREDL)
          </p>
          <p className="mt-1 text-[11px] text-slate-500">
            ENERVISION — AI-Powered Renewable Energy Forecasting & Decision-Support Platform.
            Model target: DailyGeneration_MU (MU/day). Calibrated for Karnataka SLDC operations.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-4 text-[11px] font-mono text-slate-500">
          <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-50 px-2.5 py-0.5 font-medium text-emerald-800 border border-emerald-200">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-600" />
            {API_MODE === 'live' ? 'Live backend connected' : 'Offline cache'}
          </span>
          <span>v2.0 Karnataka Release</span>
        </div>
      </div>
    </footer>
  )
}

export default function AppLayout() {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const location = useLocation()

  useEffect(() => {
    setSidebarOpen(false)
  }, [location.pathname])

  return (
    <div className="min-h-screen bg-slate-50 text-slate-800 font-sans antialiased">
      <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />

      <div className="flex min-h-screen flex-col lg:pl-[248px]">
        <Header onOpenSidebar={() => setSidebarOpen(true)} />

        <main className="mx-auto w-full max-w-[1500px] flex-1 px-3 py-6 sm:px-6 lg:px-8">
          <Outlet />
        </main>

        <Footer />
      </div>
    </div>
  )
}
