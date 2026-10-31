import React, { createContext, useContext, useEffect, useState } from 'react'

const TRANSLATIONS = {
  en: {
    govIdentity: 'Government of Karnataka · Department of Energy',
    govKredl: 'Karnataka Renewable Energy Development Ltd (KREDL)',
    portalTitle: 'ENERVISION · AI-Powered Renewable Energy Intelligence',
    liveFeed: 'Live API Feed',
    offlineFeed: 'Offline Cache',
    searchPlaceholder: 'Search plants, districts (e.g. Pavagada, Gadag)...',
    
    // Navigation
    navOverview: 'Overview',
    navForecast: 'Forecast',
    navPlants: 'Plants',
    navAnalytics: 'Analytics',
    navModels: 'Models',
    navAbout: 'About',

    // Hero / Landing
    heroTag: 'KARNATAKA RENEWABLE ENERGY DECISION-SUPPORT PORTAL',
    heroTitle: 'Forecasting Karnataka’s Clean Energy Future',
    heroSubtitle: 'Plant-wise daily generation forecasts, atmospheric weather intelligence, and machine-learning explainability for Karnataka’s grid operators and policymakers.',
    exploreForecastsBtn: 'Explore Forecasts',
    viewDashboardBtn: 'View Dashboard',

    // KPI Cards
    totalPlants: 'Monitored Assets',
    totalCapacity: 'Installed Capacity',
    currentGeneration: 'Observed Daily Generation',
    nextForecast: 'Next 24h Generation Forecast',
    fleetCoverage: 'Fleet Reporting Coverage',
    solarCapacity: 'Solar Capacity',
    windCapacity: 'Wind Capacity',
    solarGeneration: 'Solar Generation',
    windGeneration: 'Wind Generation',
    reportingStatus: 'Reporting Assets',

    // Common labels
    unitMU: 'MU/day',
    unitGW: 'GW',
    unitMW: 'MW',
    solar: 'Solar',
    wind: 'Wind',
    all: 'All',
    district: 'District',
    capacity: 'Capacity',
    loading: 'Loading data...',
    retry: 'Retry',
    noData: 'No data available',
    confidenceNote: 'Statistical prediction intervals calibrated on held-out test evaluation.',
  },
  kn: {
    govIdentity: 'ಕರ್ನಾಟಕ ಸರ್ಕಾರ · ಇಂಧನ ಇಲಾಖೆ',
    govKredl: 'ಕರ್ನಾಟಕ ನವೀಕರಿಸಬಹುದಾದ ಇಂಧನ ಅಭಿವೃದ್ಧಿ ನಿಯಮಿತ (KREDL)',
    portalTitle: 'ಎನರ್ವಿಷನ್ · ಕೃತಕ ಬುದ್ಧಿಮತ್ತೆ ಆಧಾರಿತ ನವೀಕರಿಸಬಹುದಾದ ಇಂಧನ ಮುನ್ಸೂಚನೆ',
    liveFeed: 'ನೇರ ಎಪಿಐ ಸಂಪರ್ಕ',
    offlineFeed: 'ಆಫ್‌ಲೈನ್ ಮಾಹಿತಿ',
    searchPlaceholder: 'ಸ್ಥಾವರ, ಜಿಲ್ಲೆ ಹುಡುಕಿ (ಉದಾ: ಪಾವಗಡ, ಗದಗ)...',

    // Navigation
    navOverview: 'ಅವಲೋಕನ',
    navForecast: 'ಮುನ್ಸೂಚನೆ',
    navPlants: 'ಸ್ಥಾವರಗಳು',
    navAnalytics: 'ವಿಶ್ಲೇಷಣೆ',
    navModels: 'ಮಾದರಿಗಳು',
    navAbout: 'ಮಾಹಿತಿ',

    // Hero / Landing
    heroTag: 'ಕರ್ನಾಟಕ ನವೀಕರಿಸಬಹುದಾದ ಇಂಧನ ನಿರ್ಧಾರ-ಬೆಂಬಲ ಪೋರ್ಟಲ್',
    heroTitle: 'ಕರ್ನಾಟಕದ ಶುದ್ಧ ಇಂಧನ ಭವಿಷ್ಯದ ಮುನ್ಸೂಚನೆ',
    heroSubtitle: 'ಕರ್ನಾಟಕದ ವಿದ್ಯುತ್ ಗ್ರಿಡ್ ನಿರ್ವಾಹಕರು ಮತ್ತು ನೀತಿ ನಿರೂಪಕರಿಗಾಗಿ ಸ್ಥಾವರ-ವಾರು ದೈನಂದಿನ ವಿದ್ಯುತ್ ಉತ್ಪಾದನಾ ಮುನ್ಸೂಚನೆ ಹಾಗೂ ವಾತಾವರಣ ಬುದ್ಧಿಮತ್ತೆ.',
    exploreForecastsBtn: 'ಮುನ್ಸೂಚನೆ ಪರಿಶೀಲಿಸಿ',
    viewDashboardBtn: 'ಡ್ಯಾಶ್‌ಬೋರ್ಡ್ ವೀಕ್ಷಿಸಿ',

    // KPI Cards
    totalPlants: 'ಒಟ್ಟು ಸ್ಥಾವರಗಳು',
    totalCapacity: 'ಒಟ್ಟು ಸಾಮರ್ಥ್ಯ',
    currentGeneration: 'ದೈನಂದಿನ ವಿದ್ಯುತ್ ಉತ್ಪಾದನೆ',
    nextForecast: 'ಮುಂದಿನ 24 ಗಂಟೆ ಮುನ್ಸೂಚನೆ',
    fleetCoverage: 'ವರದಿ ವ್ಯಾಪ್ತಿ',
    solarCapacity: 'ಸೌರ ಸಾಮರ್ಥ್ಯ',
    windCapacity: 'ಪವನ ಸಾಮರ್ಥ್ಯ',
    solarGeneration: 'ಸೌರ ಉತ್ಪಾದನೆ',
    windGeneration: 'ಪವನ ಉತ್ಪಾದನೆ',
    reportingStatus: 'ವರದಿ ನೀಡುತ್ತಿರುವ ಸ್ಥಾವರಗಳು',

    // Common labels
    unitMU: 'ದಶಲಕ್ಷ ಯೂನಿಟ್/ದಿನ',
    unitGW: 'ಗಿಗಾವ್ಯಾಟ್',
    unitMW: 'ಮೆಗಾವ್ಯಾಟ್',
    solar: 'ಸೌರ',
    wind: 'ಪವನ',
    all: 'ಎಲ್ಲಾ',
    district: 'ಜಿಲ್ಲೆ',
    capacity: 'ಸಾಮರ್ಥ್ಯ',
    loading: 'ಮಾಹಿತಿ ಲೋಡ್ ಆಗುತ್ತಿದೆ...',
    retry: 'ಮತ್ತೆ ಪ್ರಯತ್ನಿಸಿ',
    noData: 'ಮಾಹಿತಿ ಲಭ್ಯವಿಲ್ಲ',
    confidenceNote: 'ಪರೀಕ್ಷಾ ದತ್ತಾಂಶದ ಆಧಾರದ ಮೇಲೆ ಮಾಪನಾಂಕ ನಿರ್ಣಯಿಸಲಾದ ಸಂಖ್ಯಾಶಾಸ್ತ್ರೀಯ ಮುನ್ಸೂಚನೆ ಶ್ರೇಣಿ.',
  },
}

const LanguageContext = createContext({
  language: 'en',
  setLanguage: () => {},
  t: (key) => key,
})

export function LanguageProvider({ children }) {
  const [language, setLanguageState] = useState(() => {
    try {
      return localStorage.getItem('enervision_lang') || 'en'
    } catch {
      return 'en'
    }
  })

  const setLanguage = (lang) => {
    setLanguageState(lang)
    try {
      localStorage.setItem('enervision_lang', lang)
    } catch {
      // Ignore storage errors
    }
  }

  const t = (key) => {
    return TRANSLATIONS[language]?.[key] || TRANSLATIONS.en?.[key] || key
  }

  return (
    <LanguageContext.Provider value={{ language, setLanguage, t }}>
      {children}
    </LanguageContext.Provider>
  )
}

export function useLanguage() {
  return useContext(LanguageContext)
}
