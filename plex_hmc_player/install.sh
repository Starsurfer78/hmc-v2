#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 fehlt"
  exit 1
fi

if [ ! -d "../venv" ]; then
  python3 -m venv ../venv
fi

source ../venv/bin/activate
pip install -r backend/requirements.txt

echo "Install ok. Naechster Schritt: python3 setup.py"
