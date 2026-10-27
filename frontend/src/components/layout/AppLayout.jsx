import { useEffect, useState } from 'react'
import { Outlet, useLocation } from 'react-router-dom'
import Header from './Header.jsx'
import Sidebar from './Sidebar.jsx'
import { API_MODE } from '../../services/api.js'

function Footer() {
  return (
    <footer className="mt-8 border-t border-graphite-800 px-4 py-6 sm:px-6 lg:px-8">
      <div className="mx-auto flex max-w-[1500px] flex-col items-start justify-between gap-3 text-[11px] text-graphite-500 sm:flex-row sm:items-center">
        <p>
          <span className="font-display font-bold text-graphite-300">ENERVISION</span> — AI-Powered Renewable Energy
          Forecasting & Decision-Support Platform for Karnataka.
        </p>
        <p className="flex items-center gap-3 font-mono uppercase tracking-wide">
          <span>Frontend v2.0</span>
          <span className="hidden h-3 w-px bg-graphite-700 sm:block" />
          <span>{API_MODE} mode</span>
        </p>
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
    <div className="min-h-screen">
      <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />

      <div className="flex min-h-screen flex-col lg:pl-[248px]">
        <Header onOpenSidebar={() => setSidebarOpen(true)} />

        <main className="mx-auto w-full max-w-[1500px] flex-1 px-3 py-5 sm:px-5 lg:px-7 lg:py-7">
          <Outlet />
        </main>

        <Footer />
      </div>
    </div>
  )
}
