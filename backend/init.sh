#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${ROOT_DIR}"

echo "[backend:init] root=${ROOT_DIR}"

if [[ ! -d .venv ]]; then
  python -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate
pip install -r requirements.txt

if [[ ! -f .env && -f .env.example ]]; then
  cp .env.example .env
fi

echo "[backend:init] complete"
echo "run: source .venv/bin/activate && uvicorn app.main:app --reload --port 8000"
echo "bootstrap: pwsh ../scripts/session-bootstrap.ps1 -WorkDir .. -CountRemaining"

