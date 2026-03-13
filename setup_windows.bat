@echo off
REM FaceSearch Pro — Windows Setup Script
REM Run this once before first launch.

echo ============================================
echo   FaceSearch Pro - Windows Setup
echo ============================================
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found. Please install Python 3.10+ from python.org
    pause
    exit /b 1
)

echo [1/5] Upgrading pip...
python -m pip install --upgrade pip

echo.
echo [2/5] Installing cmake (required for dlib)...
pip install cmake

echo.
echo [3/5] Installing dlib...
echo NOTE: This may take several minutes and requires Visual Studio Build Tools.
echo       If it fails, download a prebuilt wheel from:
echo       https://github.com/z-mahmud22/Dlib_Windows_Python3.x
pip install dlib

echo.
echo [4/5] Installing face_recognition...
pip install face_recognition

echo.
echo [5/5] Installing remaining dependencies...
pip install PyQt6 opencv-python numpy Pillow

echo.
echo ============================================
echo   Setup complete! Run: python main.py
echo ============================================
pause
