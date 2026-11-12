#!/usr/bin/env bash
# ==========================================================================
#  DocExtract Pro - start without Docker (Linux / macOS)
#    ./start-linux.sh            install what is missing, then start
#    ./start-linux.sh rebuild    also rebuild the web app (after updates)
#  Needs Python 3.10-3.12 (3.11 recommended). Node.js 20 only if the web app
#  is not built yet (frontend/dist).
# ==========================================================================
set -euo pipefail
cd "$(dirname "$0")"
VENV_DIR="${VENV_DIR:-.venv}"
PY="$VENV_DIR/bin/python"

if [ ! -f .env ]; then
    cp .env.example .env
    echo "Created .env from .env.example. Fill in SECRET_KEY, APP_ADMIN_USERNAME,"
    echo "APP_ADMIN_PASSWORD, WHATSAPP_APP_SECRET, WHATSAPP_VERIFY_TOKEN and your AI key,"
    echo "then run this script again."
    exit 1
fi

if [ ! -x "$PY" ]; then
    PYCMD=""
    for v in python3.11 python3.12 python3.10; do
        if command -v "$v" >/dev/null 2>&1; then PYCMD="$v"; break; fi
    done
    if [ -z "$PYCMD" ]; then
        echo "Python 3.11 not found. Install it (e.g. sudo apt install python3.11 python3.11-venv) and retry."
        exit 1
    fi
    echo "Creating the Python environment with $PYCMD..."
    "$PYCMD" -m venv "$VENV_DIR"
fi

echo "Checking Python packages..."
"$PY" -m pip install --disable-pip-version-check -q --upgrade pip
"$PY" -m pip install --disable-pip-version-check -q -r backend/requirements.txt
if grep -qiE '^INSTALL_OCR=true' .env; then
    echo "Checking OCR packages (large download on the first run)..."
    "$PY" -m pip install --disable-pip-version-check -q -r backend/requirements-ocr.txt
fi

if [ "${1:-}" = "rebuild" ] || [ ! -f frontend/dist/index.html ]; then
    command -v npm >/dev/null 2>&1 || { echo "Install Node.js 20 LTS (https://nodejs.org) to build the web app."; exit 1; }
    echo "Building the web app..."
    (cd frontend && npm ci --no-audit --no-fund && npm run build)
fi

export SERVE_FRONTEND=true
exec "$PY" -m backend.serve
