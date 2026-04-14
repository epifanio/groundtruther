<#
.SYNOPSIS
    Install GroundTruther QGIS plugin dependencies on Windows.

.DESCRIPTION
    Locates the Python interpreter bundled with your QGIS standalone
    installation and installs all required packages into it.

    Run once before enabling the plugin.  Re-run after a QGIS upgrade
    that changes the Python version.

.NOTES
    If QGIS is installed in "C:\Program Files\" you must run this script
    as Administrator (right-click → "Run with PowerShell as Administrator").
    If you installed QGIS into your user directory no elevation is needed.

.EXAMPLE
    # From a PowerShell prompt in the plugin directory:
    Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
    .\setup_windows.ps1
#>

[CmdletBinding()]
param(
    # Override auto-detection and supply the Python path directly, e.g.:
    #   .\setup_windows.ps1 -QgisPython "C:\Program Files\QGIS 3.34\apps\Python312\python.exe"
    [string]$QgisPython = ""
)

$ErrorActionPreference = "Stop"

# ── Banner ────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "  GroundTruther – Windows dependency setup" -ForegroundColor Cyan
Write-Host "  ─────────────────────────────────────────" -ForegroundColor Cyan
Write-Host ""

# ── 1. Locate QGIS Python ─────────────────────────────────────────────────────
if ($QgisPython -ne "" -and (Test-Path $QgisPython)) {
    Write-Host "Using supplied Python: $QgisPython" -ForegroundColor Green
} else {
    Write-Host "Auto-detecting QGIS Python..." -ForegroundColor Yellow

    # Standalone installer: C:\Program Files\QGIS X.YY\apps\PythonXXX\python.exe
    # OSGeo4W installer:    C:\OSGeo4W\apps\PythonXXX\python.exe
    $searchRoots = @(
        "C:\Program Files",
        "C:\Program Files (x86)",
        "C:\OSGeo4W",
        "$env:LOCALAPPDATA\Programs"     # user-level installs
    )

    $QgisPython = $null
    foreach ($root in $searchRoots) {
        if (-not (Test-Path $root)) { continue }
        $found = Get-ChildItem $root -Filter "python.exe" -Recurse -ErrorAction SilentlyContinue |
                 Where-Object { $_.FullName -match "QGIS|OSGeo4W" } |
                 Sort-Object { $_.FullName } -Descending |   # prefer newer versions
                 Select-Object -First 1
        if ($found) {
            $QgisPython = $found.FullName
            break
        }
    }

    if (-not $QgisPython) {
        Write-Host ""
        Write-Host "ERROR: Could not find a QGIS Python installation." -ForegroundColor Red
        Write-Host ""
        Write-Host "  Please supply the path explicitly, for example:" -ForegroundColor Yellow
        Write-Host '  .\setup_windows.ps1 -QgisPython "C:\Program Files\QGIS 3.34\apps\Python312\python.exe"' -ForegroundColor Yellow
        Write-Host ""
        Write-Host "  Common locations:" -ForegroundColor Yellow
        Write-Host "    C:\Program Files\QGIS 3.34\apps\Python312\python.exe"
        Write-Host "    C:\Program Files\QGIS 3.38\apps\Python312\python.exe"
        Write-Host "    C:\OSGeo4W\apps\Python312\python.exe"
        exit 1
    }

    Write-Host "Found: $QgisPython" -ForegroundColor Green
}

# Confirm it is actually Python
$pyVersion = & $QgisPython --version 2>&1
Write-Host "Version: $pyVersion" -ForegroundColor DarkGray
Write-Host ""

# ── 2. Resolve requirements.txt path ─────────────────────────────────────────
$scriptDir   = Split-Path -Parent $MyInvocation.MyCommand.Path
$reqFile     = Join-Path $scriptDir "dependencies\requirements.txt"
if (-not (Test-Path $reqFile)) {
    Write-Host "ERROR: requirements.txt not found at: $reqFile" -ForegroundColor Red
    exit 1
}

# ── 3. Upgrade pip ───────────────────────────────────────────────────────────
Write-Host "Upgrading pip..." -ForegroundColor Yellow
& $QgisPython -m pip install --upgrade pip --quiet
if ($LASTEXITCODE -ne 0) {
    Write-Host "WARNING: pip upgrade failed (non-fatal, continuing)." -ForegroundColor Yellow
}

# ── 4. Install packages ───────────────────────────────────────────────────────
Write-Host "Installing packages from requirements.txt..." -ForegroundColor Yellow
Write-Host ""

# Install all packages at once via -r (handles version specifiers safely)
Write-Host "  Running: pip install -r requirements.txt" -ForegroundColor DarkGray
Write-Host ""

$output = & $QgisPython -m pip install -r $reqFile 2>&1
$exitCode = $LASTEXITCODE

# Show pip output
$output | ForEach-Object { Write-Host "  $_" }

$failed = @()
if ($exitCode -ne 0) {
    # pip already printed which package(s) failed; collect them for the summary
    $output | Where-Object { $_ -match "ERROR" } | ForEach-Object { $failed += $_ }
}

# ── 5. Report ─────────────────────────────────────────────────────────────────
Write-Host ""
if ($exitCode -eq 0) {
    Write-Host "All packages installed successfully." -ForegroundColor Green
} else {
    Write-Host "One or more packages failed to install (see output above)." -ForegroundColor Red
    Write-Host ""
    Write-Host "You can retry individual packages from the OSGeo4W Shell:" -ForegroundColor Yellow
    Write-Host "  pip install <package-name>"
    Write-Host ""
}

# ── 6. Plugin location reminder ───────────────────────────────────────────────
$pluginDir = "$env:APPDATA\QGIS\QGIS3\profiles\default\python\plugins"
Write-Host ""
Write-Host "Plugin deployment" -ForegroundColor Cyan
Write-Host "─────────────────" -ForegroundColor Cyan
Write-Host "Copy or symlink the 'groundtruther' folder into:" -ForegroundColor Yellow
Write-Host "  $pluginDir\groundtruther\" -ForegroundColor White
Write-Host ""
Write-Host "To create a symbolic link from the repo (run as Administrator):" -ForegroundColor Yellow
Write-Host "  cmd /c mklink /D `"$pluginDir\groundtruther`" `"$(Split-Path -Parent $scriptDir)\groundtruther`"" -ForegroundColor White
Write-Host ""
Write-Host "Then restart QGIS and enable the plugin via Plugins → Manage and Install Plugins." -ForegroundColor Cyan
Write-Host ""
