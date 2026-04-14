@echo off
:: GroundTruther – Windows dependency setup launcher
:: Double-click this file, or run from a command prompt.
:: If QGIS is installed in C:\Program Files you may need to right-click
:: and choose "Run as administrator".

echo.
echo  Launching GroundTruther setup...
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup_windows.ps1"

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo  Setup encountered an error.  See messages above.
    pause
    exit /b %ERRORLEVEL%
)

pause
