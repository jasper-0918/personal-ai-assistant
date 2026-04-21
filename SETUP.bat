@echo off
title Jasper AI — First Time Setup
color 0B

echo.
echo  ==========================================
echo    JASPER AI — Setup Script
echo    This runs once. Takes 5-15 minutes.
echo  ==========================================
echo.

:: Check Python
python --version > nul 2>&1
if errorlevel 1 (
    echo  ERROR: Python is not installed or not in PATH.
    echo  Download from: https://www.python.org/downloads/
    echo  Make sure to check "Add Python to PATH" during install!
    pause
    exit /b 1
)

echo  Python found.

:: Create virtual environment
echo.
echo  Step 1: Creating virtual environment...
python -m venv venv
call venv\Scripts\activate.bat
echo  Done.

:: Upgrade pip
echo.
echo  Step 2: Upgrading pip...
python -m pip install --upgrade pip --quiet

:: Install dependencies
echo.
echo  Step 3: Installing packages (this takes a few minutes)...
pip install -r requirements.txt
echo  Done.

:: Run ingest to load starter knowledge
echo.
echo  Step 4: Loading your starter knowledge...
python ingest.py
echo  Done.

echo.
echo  ==========================================
echo    Setup complete!
echo.
echo    Next: Make sure Ollama is installed.
echo    Download from: https://ollama.com
echo    Then run: ollama pull phi3:mini
echo.
echo    After that, double-click START.bat
echo    to launch your AI assistant.
echo  ==========================================
echo.
pause
