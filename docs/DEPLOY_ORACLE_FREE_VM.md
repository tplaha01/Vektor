# Deploy Backend on Oracle Free VM (24/7 Baseline)

This runbook deploys the **Vektor backend** to an Oracle Always Free VM, while keeping:

- Frontend on Vercel
- OpenClaw + Ollama on your laptop

This is the fastest low-cost traction setup.

## Architecture

- `Vercel`: frontend(s)
- `Oracle VM`: FastAPI backend on port `8000` (systemd)
- `Laptop`: OpenClaw + local LLMs (Ollama), calling backend APIs

If the laptop is offline, backend should stay in safe mode (`hold_cash` / no execution).

## 1) Provision Oracle VM

Use an Always Free eligible shape and Ubuntu image.

Recommended:
- Shape: `VM.Standard.A1.Flex` within Always Free limits
- OS: Ubuntu 22.04+

Open inbound:
- `22` (SSH)
- `8000` (backend API)  
Or keep `8000` private and expose only through your own tunnel/proxy.

## 2) Clone Repo on VM

```bash
git clone https://github.com/tplaha01/Vektor.git ~/Vektor
cd ~/Vektor
```

## 3) Run Oracle Setup Script

```bash
chmod +x scripts/oracle/setup_oracle_backend.sh scripts/oracle/backup_backend.sh
./scripts/oracle/setup_oracle_backend.sh ~/Vektor "$(whoami)" "$HOME/vektor-backups"
```

What it does:
- installs OS deps
- creates `backend/.venv`
- installs `backend/requirements.cloud.txt`
- installs and enables:
  - `vektor-backend.service`
  - `vektor-backup.timer` (daily backups)

## 4) Configure Backend Env

Edit:

```bash
nano ~/Vektor/backend/.env
```

Minimum production keys:
- `ENV=production`
- `API_KEY=<long-random>`
- `SECRET_KEY=<long-random>`
- provider keys (`ALPACA_*`, `NEWSAPI_KEY`, etc.)
- `FRONTEND_URL=<your vercel url>`

### Sentry Alerts

Set:
- `SENTRY_DSN=<your sentry dsn>`
- `SENTRY_ENVIRONMENT=production`
- `SENTRY_TRACES_SAMPLE_RATE=0.0` (start low)
- `SENTRY_PROFILES_SAMPLE_RATE=0.0`

Sentry auto-initializes in backend startup when `SENTRY_DSN` is present.

## 5) Restart and Verify

```bash
sudo systemctl restart vektor-backend
sudo systemctl status vektor-backend --no-pager
curl -s http://127.0.0.1:8000/health | jq
```

Follow logs:

```bash
sudo journalctl -u vektor-backend -f
```

## 6) Backup Verification

Run immediate backup once:

```bash
sudo systemctl start vektor-backup.service
ls -lah ~/vektor-backups
```

Timer check:

```bash
systemctl list-timers | grep vektor-backup
```

Default retention: 14 days (configurable via `KEEP_DAYS` in script env).

## 7) OpenClaw + Laptop Integration

Run OpenClaw and Ollama on laptop, and point command/orchestration flows to the cloud backend.

Recommended:
- keep backend API protected with `X-API-Key`
- avoid exposing local Ollama publicly
- use secure private networking/tunnel for any laptop-to-cloud link

## Ops Notes

- Oracle Always Free capacity can fluctuate by region.
- Always Free instances can be reclaimed if considered idle.
- Keep a redeploy script and backups so recovery is quick.

