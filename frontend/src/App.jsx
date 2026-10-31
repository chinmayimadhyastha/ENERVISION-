import { Route, Routes } from 'react-router-dom'
import { LanguageProvider } from './context/LanguageContext.jsx'
import AppLayout from './components/layout/AppLayout.jsx'
import Dashboard from './pages/Dashboard.jsx'
import Plants from './pages/Plants.jsx'
import PlantDetails from './pages/PlantDetails.jsx'
import Forecast from './pages/Forecast.jsx'
import Analytics from './pages/Analytics.jsx'
import ModelPerformance from './pages/ModelPerformance.jsx'
import About from './pages/About.jsx'
import NotFound from './pages/NotFound.jsx'

export default function App() {
  return (
    <LanguageProvider>
      <Routes>
        <Route element={<AppLayout />}>
          <Route index element={<Dashboard />} />
          <Route path="plants" element={<Plants />} />
          <Route path="plants/:plantId" element={<PlantDetails />} />
          <Route path="forecast" element={<Forecast />} />
          <Route path="analytics" element={<Analytics />} />
          <Route path="model-performance" element={<ModelPerformance />} />
          <Route path="about" element={<About />} />
          <Route path="*" element={<NotFound />} />
        </Route>
      </Routes>
    </LanguageProvider>
  )
}
