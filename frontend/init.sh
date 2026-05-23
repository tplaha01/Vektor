#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${ROOT_DIR}"

echo "[frontend:init] root=${ROOT_DIR}"

npm install

if [[ ! -f .env && -f .env.example ]]; then
  cp .env.example .env
fi

echo "[frontend:init] complete"
echo "run: npm run dev"
echo "bootstrap: pwsh ../scripts/session-bootstrap.ps1 -WorkDir .. -CountRemaining"

