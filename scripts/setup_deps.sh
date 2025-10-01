#!/usr/bin/env bash
set -euo pipefail

# Create venv, install deps, download wheels (with all dependencies),
# and vendor-install into ./vendor for Blender to use offline.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")"/.. && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-python3}"
VENV_DIR="${VENV_DIR:-.venv}"

echo "[1/6] Creating virtualenv at $VENV_DIR"
"$PYTHON_BIN" -m venv "$VENV_DIR"

if [[ -f "$VENV_DIR/bin/activate" ]]; then
  # POSIX
  source "$VENV_DIR/bin/activate"
elif [[ -f "$VENV_DIR/Scripts/activate" ]]; then
  # Windows Git Bash
  source "$VENV_DIR/Scripts/activate"
else
  echo "Could not find venv activation script." >&2
  exit 1
fi

echo "[2/6] Upgrading pip/setuptools/wheel"
python -m pip install --upgrade pip setuptools wheel

echo "[3/6] Installing runtime dependencies into venv"
python -m pip install -r requirements.txt

echo "[4/6] Resolving and downloading wheels for all deps"
mkdir -p wheels vendor
python -m pip download -d wheels -r requirements.txt

echo "[5/6] Vendoring deps into ./vendor (from local wheels)"
python -m pip install --no-index --find-links wheels -t vendor -r requirements.txt

echo "[6/6] Verifying vendored imports"
python - <<'PY'
import sys
sys.path.insert(0, 'vendor')
import can, canopen
print('python-can:', getattr(can, '__version__', 'unknown'))
print('canopen:', getattr(canopen, '__version__', 'unknown'))
PY

echo "Done. Wheels are in ./wheels; vendored libs in ./vendor."

