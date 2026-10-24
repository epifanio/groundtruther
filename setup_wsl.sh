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
# The venv MUST be `.venv`, beside the plugin source: that is the one path
# `__init__.py`'s _bootstrap_venv() appends to sys.path, so a venv anywhere else
# or under any other name is one the plugin never loads.  This script used to
# create `gtenv` in the current directory, which was exactly that bug.
HERE="$(cd "$(dirname "$0")" && pwd)"
VENV="$HERE/.venv"

echo "==> Using pip venv (--system-site-packages) at $VENV"
python3 -m venv --system-site-packages "$VENV"
# shellcheck disable=SC1091
source "$VENV/bin/activate"
pip install --upgrade pip
pip install -r "$HERE/dependencies/requirements.txt"

echo ""
echo "==> Done.  QGIS picks these up on its own: _bootstrap_venv() appends"
echo "    $VENV to sys.path when the plugin loads."
echo "    To use the same interpreter yourself:"
echo "      source $VENV/bin/activate"
