#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="${1:-$HOME/Vektor}"
APP_USER="${2:-$(whoami)}"
API_HOST="${3:-}"

BACKEND_DIR="$REPO_DIR/backend"
VENV_DIR="$BACKEND_DIR/.venv"
SERVICE_NAME="vektor-backend.service"

if [[ ! -d "$BACKEND_DIR" ]]; then
  echo "Backend directory not found: $BACKEND_DIR" >&2
  exit 1
fi

set_or_append_env() {
  local key="$1"
  local value="$2"
  local file="$3"
  if grep -qE "^${key}=" "$file"; then
    sed -i "s|^${key}=.*|${key}=${value}|" "$file"
  else
    printf "\n%s=%s\n" "$key" "$value" >> "$file"
  fi
}

echo "[1/6] Installing system packages..."
sudo apt-get update -y
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y \
  python3-venv python3-pip build-essential libgomp1 rsync curl jq git \
  ca-certificates debian-keyring debian-archive-keyring apt-transport-https

echo "[2/6] Installing backend Python environment..."
python3 -m venv "$VENV_DIR"
"$VENV_DIR/bin/pip" install --upgrade pip wheel setuptools
"$VENV_DIR/bin/pip" install -r "$BACKEND_DIR/requirements.txt"

if [[ ! -f "$BACKEND_DIR/.env" ]]; then
  cp "$BACKEND_DIR/.env.example" "$BACKEND_DIR/.env"
  echo "Created $BACKEND_DIR/.env from example; replace secrets before production use."
fi

set_or_append_env "ENV" "prod" "$BACKEND_DIR/.env"
set_or_append_env "BROKER" "paper" "$BACKEND_DIR/.env"
set_or_append_env "DETERMINISTIC_RUNTIME_MODE" "true" "$BACKEND_DIR/.env"
set_or_append_env "REAL_DATA_STRICT_MODE" "true" "$BACKEND_DIR/.env"
set_or_append_env "AUTO_TRADING_ENABLED" "false" "$BACKEND_DIR/.env"
set_or_append_env "LIVE_TRADING_ENABLED" "false" "$BACKEND_DIR/.env"
set_or_append_env "AI_ROLE_ADAPTER_ENABLED" "false" "$BACKEND_DIR/.env"
set_or_append_env "AI_ROLE_ROUTER_ENABLED" "false" "$BACKEND_DIR/.env"
set_or_append_env "AGENT_RUNTIME_ENABLED" "false" "$BACKEND_DIR/.env"
set_or_append_env "AGENT_RUNTIME_AUTOPILOT_ENABLED" "false" "$BACKEND_DIR/.env"
set_or_append_env "DATA_PIPELINE_ENABLED" "true" "$BACKEND_DIR/.env"

mkdir -p "$REPO_DIR/knowledge_graph" "$REPO_DIR/.run" "$BACKEND_DIR/logs"
touch "$REPO_DIR/knowledge_graph/events.jsonl"
sudo chown -R "$APP_USER:$APP_USER" "$REPO_DIR/knowledge_graph" "$REPO_DIR/.run" "$BACKEND_DIR/logs"

echo "[3/6] Installing backend systemd service..."
sudo tee "/etc/systemd/system/$SERVICE_NAME" >/dev/null <<EOF
[Unit]
Description=Vektor Backend API
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$APP_USER
WorkingDirectory=$BACKEND_DIR
Environment=PYTHONUNBUFFERED=1
ExecStart=$VENV_DIR/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1
Restart=always
RestartSec=5
TimeoutStopSec=20

[Install]
WantedBy=multi-user.target
EOF

echo "[4/6] Installing Caddy reverse proxy..."
if ! command -v caddy >/dev/null 2>&1; then
  curl -1sLf "https://dl.cloudsmith.io/public/caddy/stable/gpg.key" | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
  curl -1sLf "https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt" | sudo tee /etc/apt/sources.list.d/caddy-stable.list >/dev/null
  sudo apt-get update -y
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y caddy
fi

if [[ -n "$API_HOST" ]]; then
  sudo tee /etc/caddy/Caddyfile >/dev/null <<EOF
$API_HOST {
  encode zstd gzip
  reverse_proxy 127.0.0.1:8000
}
EOF
else
  sudo tee /etc/caddy/Caddyfile >/dev/null <<'EOF'
:80 {
  encode zstd gzip
  reverse_proxy 127.0.0.1:8000
}
EOF
fi

echo "[5/6] Starting services..."
sudo systemctl daemon-reload
sudo systemctl enable --now "$SERVICE_NAME"
sudo systemctl enable --now caddy
sudo systemctl reload caddy || sudo systemctl restart caddy

echo "[6/6] Health check..."
sleep 5
curl -fsS http://127.0.0.1:8000/health | head -c 1200
echo
