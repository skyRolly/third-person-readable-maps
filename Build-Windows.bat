@echo off
setlocal
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Build-Windows.ps1"
if errorlevel 1 (
  echo.
  echo Build failed. See error messages above.
  pause
  exit /b 1
)
echo.
echo Build completed.
pause
