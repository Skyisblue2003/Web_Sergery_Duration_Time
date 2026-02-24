@echo off
title Surgery Prediction System - Auto Runner
cls
echo ======================================================
echo    Surgery Prediction System: Auto-Installation
echo ======================================================
echo.

:: 1. เช็คว่ามี Python หรือไม่
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed. Please install Python first.
    pause
    exit
)

:: 2. สร้าง Virtual Environment
if not exist "venv" (
    echo [1/4] Creating Virtual Environment (venv)...
    python -m venv venv
) else (
    echo [1/4] Virtual Environment already exists.
)

:: 3. ติดตั้ง Library
echo [2/4] Installing requirements... This may take a while...
call venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt

:: 4. เตรียม Database
echo [3/4] Preparing Database (Migration)...
python manage.py migrate

:: 5. เปิดหน้าเว็บและรัน Server
echo [4/4] Starting Server...
echo.
echo ------------------------------------------------------
echo  SUCCESS! The system is starting.
echo  Please visit: http://127.0.0.1:8000
echo ------------------------------------------------------
echo.
start http://127.0.0.1:8000
python manage.py runserver

pause