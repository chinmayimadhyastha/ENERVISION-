@echo off
title ENERVISION - Karnataka Renewable Energy Platform
echo ======================================================================
echo  ENERVISION - Official Decision-Support Platform
echo  Starting Backend (Flask :5000) and Frontend (Vite :5173)...
echo ======================================================================

start "ENERVISION Backend (Port 5000)" cmd /k "cd /d %~dp0 && .\.venv\Scripts\python.exe backend/app.py"
start "ENERVISION Frontend (Port 5173)" cmd /k "cd /d %~dp0\frontend && npm run dev"

echo.
echo Both servers have been launched in separate windows!
echo - Backend API:  http://localhost:5000/api/health
echo - Web Portal:   http://localhost:5173
echo.
pause
