#!/usr/bin/env bash
# GroundTruther – Linux / WSL2 environment setup
#
# Preferred: mamba (conda-forge) — installs QGIS + all deps in one step.
# Fallback:  pip venv with --system-site-packages (requires QGIS already
#            installed on the host via apt / osgeo).
#
# Usage:
#   chmod +x setup_wsl.sh
#   ./setup_wsl.sh            # auto-selects mamba if available
#   ./setup_wsl.sh --venv     # force the legacy pip venv approach

set -euo pipefail

USE_VENV=0
for arg in "$@"; do
  [[ "$arg" == "--venv" ]] && USE_VENV=1
done

# ── Mamba path ────────────────────────────────────────────────────────────────
if [[ $USE_VENV -eq 0 ]] && command -v mamba &>/dev/null; then
  echo "==> mamba found – creating conda-forge environment"
  ENV_FILE="$(dirname "$0")/environment.yml"

  if mamba env list | grep -q "^groundtruther "; then
    echo "==> Environment 'groundtruther' already exists – updating"
    mamba env update --name groundtruther --file "$ENV_FILE" --prune
  else
    mamba env create --file "$ENV_FILE"
  fi

  echo ""
  echo "==> Done.  Activate with:"
  echo "      mamba activate groundtruther"
  echo "    Then launch QGIS with:  qgis"
  exit 0
fi

# ── Pip venv fallback (system QGIS must already be installed) ─────────────────
echo "==> Using pip venv (--system-site-packages)"
python3 -m venv --system-site-packages gtenv
source gtenv/bin/activate
pip install --upgrade pip
pip install -r "$(dirname "$0")/dependencies/requirements.txt"

echo ""
echo "==> Done.  Activate with:"
echo "      source gtenv/bin/activate"
