@echo off
:: GroundTruther – mamba environment setup (Windows)
:: Requires Miniforge or Mambaforge to be installed.
::
:: Run from the repository root:
::   setup_mamba.bat

setlocal

set ENV_NAME=groundtruther
set ENV_FILE=%~dp0environment.yml

echo.
echo  GroundTruther – mamba environment setup
echo  =========================================
echo.

:: ── Check mamba is on PATH ─────────────────────────────────────────────────
where mamba >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo  ERROR: mamba not found on PATH.
    echo.
    echo  Install Miniforge from:
    echo    https://github.com/conda-forge/miniforge/releases/latest
    echo  then open a new terminal and re-run this script.
    echo.
    pause
    exit /b 1
)

:: ── Create or update the environment ──────────────────────────────────────
mamba env list | findstr /C:"%ENV_NAME%" >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo  Environment "%ENV_NAME%" already exists – updating...
    mamba env update --name %ENV_NAME% --file "%ENV_FILE%" --prune
) else (
    echo  Creating environment "%ENV_NAME%"...
    mamba env create --user --file "%ENV_FILE%"
)

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo  ERROR: environment creation failed. See messages above.
    pause
    exit /b 1
)

:: ── Plugin location reminder ───────────────────────────────────────────────
set PLUGIN_DIR=%APPDATA%\QGIS\QGIS3\profiles\default\python\plugins

echo.
echo  Done!
echo.
echo  To launch QGIS from this environment:
echo    mamba activate %ENV_NAME%
echo    qgis
echo.
echo  Plugin deployment:
echo    Copy or symlink the "groundtruther" folder into:
echo      %PLUGIN_DIR%\groundtruther\
echo.
echo  To create a symbolic link from the repo (run as Administrator in cmd):
echo    mklink /D "%PLUGIN_DIR%\groundtruther" "%~dp0"
echo.

pause
