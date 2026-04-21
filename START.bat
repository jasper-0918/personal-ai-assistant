@echo off
title Jasper AI v3 — Virtual Assistant
color 0A
chcp 65001 > nul

echo.
echo  ==========================================
echo    JASPER AI v3 — Virtual Assistant
echo  ==========================================
echo.

if not exist "venv\Scripts\activate.bat" (
    echo  ERROR: Run SETUP.bat first.
    pause
    exit /b 1
)

call venv\Scripts\activate.bat
set PYTHONIOENCODING=utf-8

echo  Checking Ollama...
curl -s http://localhost:11434 > nul 2>&1
if errorlevel 1 (
    echo  Starting Ollama...
    start "" "ollama" serve
    timeout /t 4 /nobreak > nul
) else (
    echo  Ollama is running.
)

echo  Starting daemon...
start "Jasper AI Daemon" /min cmd /c "chcp 65001 && set PYTHONIOENCODING=utf-8 && call venv\Scripts\activate.bat && python daemon.py"

timeout /t 2 /nobreak > nul
echo  Opening Jasper AI at http://localhost:8501
echo.

streamlit run app_v3.py --server.headless false --server.port 8501

pause
