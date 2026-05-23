#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${ROOT_DIR}"

echo "[backend:init] root=${ROOT_DIR}"

if [[ ! -d .venv ]]; then
  python -m venv .venv
fi

if [[ -f .venv/bin/activate ]]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
elif [[ -f .venv/Scripts/activate ]]; then
  # shellcheck disable=SC1091
  source .venv/Scripts/activate
else
  echo "[backend:init] ERROR: could not find venv activation script under .venv" >&2
  exit 1
fi

pip install -r requirements.txt

if [[ ! -f .env && -f .env.example ]]; then
  cp .env.example .env
fi

echo "[backend:init] complete"
echo "run: source .venv/bin/activate (or .venv/Scripts/activate on Windows) && uvicorn app.main:app --reload --port 8000"
echo "bootstrap: pwsh ../scripts/session-bootstrap.ps1 -WorkDir .. -CountRemaining"

