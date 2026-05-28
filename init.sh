#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "[vektor:init] root: ${ROOT_DIR}"

if [[ -d "${ROOT_DIR}/backend" ]]; then
  echo "[vektor:init] backend deps"
  (
    cd "${ROOT_DIR}/backend"
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
      echo "[vektor:init] ERROR: could not find backend venv activation script under .venv" >&2
      exit 1
    fi
    pip install -r requirements.txt
  )
fi

if [[ -d "${ROOT_DIR}/frontend" && -f "${ROOT_DIR}/frontend/package.json" ]]; then
  echo "[vektor:init] frontend deps"
  (
    cd "${ROOT_DIR}/frontend"
    npm install
  )
fi

if [[ -d "${ROOT_DIR}/landing-next" && -f "${ROOT_DIR}/landing-next/package.json" ]]; then
  echo "[vektor:init] landing deps"
  (
    cd "${ROOT_DIR}/landing-next"
    npm install
  )
fi

echo "[vektor:init] complete"
echo "backend:  cd backend && source .venv/bin/activate (or .venv/Scripts/activate on Windows) && uvicorn app.main:app --reload --port 8000"
echo "frontend: cd frontend && npm run dev"
echo "landing:  cd landing-next && npm run dev"
echo "session bootstrap: bash ./scripts/session-bootstrap.sh --count-remaining"
