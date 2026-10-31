# ENERVISION — Run & Verification Guide

This guide walks you through launching the **ENERVISION** application (Backend + Frontend) and verifying the end-to-end functionality.

---

## Quick Start (One-Click)

From the project root:
- **Double click `start.bat`** (or in PowerShell run `.\start.ps1`).

This automatically opens two terminal windows:
1. **ENERVISION Backend API** on `http://localhost:5000`
2. **ENERVISION Frontend Portal** on `http://localhost:5173`

---

## Manual Step-by-Step (Two Terminals)

### Terminal 1: Start Backend (Flask API)

Open your terminal, navigate to the project directory, and run:

```powershell
cd C:\Users\barsa\.gemini\antigravity\scratch\enervision
.\.venv\Scripts\python.exe backend/app.py
```

Expected startup output:
```text
 * Serving Flask app 'backend.app_factory'
 * Debug mode: off
 * Running on http://127.0.0.1:5000
```

> **Backend Health Verification:**
> In your browser or curl, check:
> `http://localhost:5000/api/health`
> It will return `{ "status": "ok", "app": "enervision-backend", "models": { "random_forest": "loaded", "solar_lstm": "loaded", "wind_lstm": "loaded" } }`

---

### Terminal 2: Start Frontend (Vite)

In a second terminal window, navigate to the `frontend` folder and run:

```powershell
cd C:\Users\barsa\.gemini\antigravity\scratch\enervision\frontend
npm run dev
```

Expected startup output:
```text
  VITE v5.4.21  ready in ~400 ms

  ➜  Local:   http://localhost:5173/
  ➜  Network: use --host to expose
```

---

## What to Check in Your Browser

Open **`http://localhost:5173`** in your browser. You will see:

1. **Header & Government Identity:**
   - Subtle Karnataka tricolor accent ribbon (`red-600` / `amber-500` / `emerald-600`) at the top edge.
   - **"Government of Karnataka · Department of Energy"** & **"KREDL · Karnataka Renewable Energy Development Ltd"**.
   - State emblem slot with neutral administrative fallback (and slot instructions in `public/assets/README.md`).
   - Real-time backend status pill: **"Live API Feed"** with green pulse indicator.
   - Live **IST Clock** and date.
   - **Bilingual Switcher:** Click `[ಕನ್ನಡ]` to switch the entire portal into Kannada; click `[EN]` to switch back to English.

2. **Overview (Dashboard):**
   - **Portal Hero:** Karnataka Clean Energy Platform overview with quick navigation to Explore Forecasts.
   - **4 Top KPI Cards:** 37 Monitored Assets, ~3.5 GW Installed Capacity, Observed Daily Generation (`MU/day`), 24h AI Forecast Availability.
   - **Karnataka Plant Network Map:** Interactive SVG map projecting all 37 renewable plants across Karnataka districts (Pavagada, Gadag, Koppal, Bellary, Tumakuru) with proportional capacity nodes.
   - **Representative Forecast Centrepiece:** Real 2026 predictions for `kredl` with 95% empirical confidence intervals (`[lower_bound, upper_bound]`) and tree/LSTM feature attributions.

3. **Forecast Page (`/forecast`):**
   - Select any plant (e.g. `kredl`, `gadag-vena-w`, `amplus-pavagada`).
   - Select model: `Auto`, `Random Forest`, or `LSTM`.
   - Select forecast horizon: 1 to 7 days.
   - Click "Run Forecast" or change controls to observe real daily generation predictions in `MU/day` and calibrated uncertainty bounds.

4. **Plant Explorer (`/plants` & `/plants/:id`):**
   - Browse the 37 monitored assets filtered by Solar vs Wind and Karnataka districts.
   - Click any plant to inspect historical generation, metadata, and weather telemetry.

5. **Model Performance (`/model-performance`):**
   - Transparent reporting of MAE, RMSE, and R² across held-out evaluation datasets for Random Forest, Solar LSTM, and Wind LSTM.
