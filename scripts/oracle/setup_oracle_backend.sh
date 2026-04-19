#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="${1:-$HOME/Vektor}"
APP_USER="${2:-$(whoami)}"
BACKUP_ROOT="${3:-$HOME/vektor-backups}"

BACKEND_DIR="$REPO_DIR/backend"
VENV_DIR="$BACKEND_DIR/.venv"
SERVICE_NAME="vektor-backend.service"
BACKUP_SERVICE_NAME="vektor-backup.service"
BACKUP_TIMER_NAME="vektor-backup.timer"

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

if [[ ! -d "$BACKEND_DIR" ]]; then
  echo "Backend directory not found: $BACKEND_DIR"
  echo "Clone the repo first or pass REPO_DIR explicitly."
  exit 1
fi

echo "[1/7] Installing system packages..."
sudo apt-get update -y
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y \
  python3-venv \
  python3-pip \
  build-essential \
  libgomp1 \
  rsync \
  curl \
  jq

echo "[2/7] Creating backend virtual environment..."
python3 -m venv "$VENV_DIR"
"$VENV_DIR/bin/pip" install --upgrade pip wheel setuptools

echo "[3/7] Installing cloud requirements..."
"$VENV_DIR/bin/pip" install -r "$BACKEND_DIR/requirements.cloud.txt"

if [[ ! -f "$BACKEND_DIR/.env" ]]; then
  echo "[4/7] No backend/.env found; copying from .env.example"
  cp "$BACKEND_DIR/.env.example" "$BACKEND_DIR/.env"
  echo "Edit $BACKEND_DIR/.env before running in production."
else
  echo "[4/7] Existing backend/.env found"
fi

set_or_append_env "ENV" "prod" "$BACKEND_DIR/.env"
set_or_append_env "BROKER" "paper" "$BACKEND_DIR/.env"
set_or_append_env "AUTO_TRADING_ENABLED" "false" "$BACKEND_DIR/.env"
set_or_append_env "REAL_DATA_STRICT_MODE" "true" "$BACKEND_DIR/.env"
echo "Enforced production safety env keys in backend/.env"

echo "[5/7] Installing backend systemd service..."
sudo tee "/etc/systemd/system/$SERVICE_NAME" >/dev/null <<EOF
[Unit]
Description=Vektor Backend API
After=network.target

[Service]
Type=simple
User=$APP_USER
WorkingDirectory=$BACKEND_DIR
Environment=PYTHONUNBUFFERED=1
ExecStart=$VENV_DIR/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
Restart=always
RestartSec=5
TimeoutStopSec=20

[Install]
WantedBy=multi-user.target
EOF

echo "[6/7] Installing backup script and timer..."
sudo install -m 0755 "$REPO_DIR/scripts/oracle/backup_backend.sh" /usr/local/bin/vektor-backup
sudo tee "/etc/systemd/system/$BACKUP_SERVICE_NAME" >/dev/null <<EOF
[Unit]
Description=Vektor Backend Backup

[Service]
Type=oneshot
User=$APP_USER
ExecStart=/usr/local/bin/vektor-backup $REPO_DIR $BACKUP_ROOT
EOF

sudo tee "/etc/systemd/system/$BACKUP_TIMER_NAME" >/dev/null <<'EOF'
[Unit]
Description=Run Vektor Backup Daily

[Timer]
OnCalendar=*-*-* 03:30:00
Persistent=true

[Install]
WantedBy=timers.target
EOF

echo "[7/7] Enabling services..."
sudo systemctl daemon-reload
sudo systemctl enable --now "$SERVICE_NAME"
sudo systemctl enable --now "$BACKUP_TIMER_NAME"

echo
echo "Setup complete."
echo "Check backend:   sudo systemctl status $SERVICE_NAME --no-pager"
echo "View logs:       sudo journalctl -u $SERVICE_NAME -f"
echo "Run backup now:  sudo systemctl start $BACKUP_SERVICE_NAME"
echo "Timer status:    systemctl list-timers | grep vektor-backup"
