@echo off
title Mzansi Insights
echo ========================================
echo   MZANSI INSIGHTS - Starting Server
echo ========================================

if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
) else (
    python -m venv venv
    call venv\Scripts\activate.bat
    pip install -r requirements.txt
)

mkdir data 2>nul
mkdir static\uploads 2>nul
mkdir templates\admin 2>nul

echo.
echo 🌐 Website: http://localhost:5000
echo 🔧 Admin:   http://localhost:5000/admin/login
echo 👤 User:    admin
echo 🔑 Pass:    admin123
echo.
echo Press CTRL+C to stop
echo ========================================

python app.py
pause