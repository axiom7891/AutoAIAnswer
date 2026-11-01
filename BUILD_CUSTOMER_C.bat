@echo off
setlocal
cd /d "%~dp0"
if not "%OS%"=="Windows_NT" goto :failed
py -3.12 -m venv .build-venv
if errorlevel 1 goto :failed
set "PY=%CD%\.build-venv\Scripts\python.exe"
"%PY%" -m pip install -r requirements.txt
if errorlevel 1 goto :failed
set QT_QPA_PLATFORM=windows
"%PY%" -m pytest tests -q -o faulthandler_timeout=60
if errorlevel 1 goto :failed
"%PY%" -m PyInstaller --noconfirm --clean --onefile --windowed --name QQMusic-CustomerC ^
  --icon assets\app.ico ^
  --add-data "ai_screenshot_assistant\web\static;ai_screenshot_assistant\web\static" ^
  --add-data "assets;assets" ^
  --hidden-import mouse ^
  --hidden-import pynput.keyboard._win32 ^
  --hidden-import pynput.mouse._win32 ^
  --hidden-import ai_screenshot_assistant.ui.native_capture ^
  --hidden-import ai_screenshot_assistant.ui.win32_capture ^
  --hidden-import ai_screenshot_assistant.capture.health ^
  --hidden-import ai_screenshot_assistant.capture.repair ^
  --hidden-import ai_screenshot_assistant.capture.win32_window_repair ^
  --hidden-import cv2 ^
  --hidden-import openpyxl ^
  --hidden-import pypdf ^
  --hidden-import docx ^
  --collect-all rapidocr_onnxruntime ^
  --collect-all onnxruntime ^
  --collect-all pypdfium2 ^
  --exclude-module AppKit --exclude-module Quartz --exclude-module pytest ^
  main.py
if errorlevel 1 goto :failed
if not exist "dist\QQMusic-CustomerC.exe" goto :failed
echo Built: %CD%\dist\QQMusic-CustomerC.exe
echo Run the EXE and complete the Windows checks in CUSTOMER-C.md before delivery.
pause
exit /b 0
:failed
echo Build FAILED. No validated Customer C executable was produced by this run.
pause
exit /b 1
