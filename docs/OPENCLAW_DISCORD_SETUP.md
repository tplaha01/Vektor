# OpenClaw Discord Setup for Vektor Command Layer

## Goal

Route Discord channel messages through OpenClaw into Vektor's command adapter:

`Discord message -> /fund/openclaw/commands -> validated role routing -> /fund/ceo/commands -> agent task bus`

## 1) Discord channel model

Create private channels in your Discord server:

- `vektor-ceo` (CEO/founder command channel)
- `vektor-research` (optional research-only commands)
- `vektor-risk` (optional risk-only commands)

Keep channels private to trusted operators.

## 2) OpenClaw channel integration

In OpenClaw:

1. Configure `Discord (Bot API)` channel.
2. Add your bot token and guild/channel permissions.
3. Set the bot to watch only Vektor private channels.
4. Configure outbound webhook/HTTP action to call:
   - `POST http://localhost:8000/fund/openclaw/commands`
   - Header: `X-OpenClaw-Token: <OPENCLAW_COMMAND_TOKEN or OPENCLAW_INGEST_TOKEN>`
   - Content-Type: `application/json`

## 3) Message payload schema

Expected payload shape:

```json
{
  "platform": "discord",
  "channel_id": "1234567890",
  "channel_name": "vektor-ceo",
  "sender_id": "99887766",
  "sender_name": "affaan",
  "message_id": "1122334455",
  "text": "research and trade aapl",
  "run_id": "run-optional",
  "target_role": "researcher",
  "priority": 8,
  "payload": {
    "symbol": "AAPL",
    "side": "buy",
    "quantity": 1,
    "price": 100,
    "sleeve": "tactical"
  }
}
```

## 4) Role routing policy

Environment controls:

- `OPENCLAW_COMMAND_CHANNEL_ALLOWLIST`
- `OPENCLAW_COMMAND_SENDER_ALLOWLIST`
- `OPENCLAW_COMMAND_ROLE_ALLOWLIST`
- `OPENCLAW_COMMAND_CHANNEL_ROLE_POLICIES`

Example strict policy:

```env
OPENCLAW_COMMAND_CHANNEL_ALLOWLIST=vektor-ceo,vektor-research,vektor-risk
OPENCLAW_COMMAND_CHANNEL_ROLE_POLICIES=vektor-ceo=researcher,sentiment_researcher,fund_manager,trader,risk_auditor;vektor-research=researcher,sentiment_researcher;vektor-risk=risk_auditor
```

## 5) Verification

Check adapter health:

```powershell
Invoke-RestMethod -Method GET -Uri "http://localhost:8000/fund/openclaw/commands/health"
```

Send a test command:

```powershell
$token = "<OPENCLAW_COMMAND_TOKEN or OPENCLAW_INGEST_TOKEN>"
$body = @{
  platform = "discord"
  channel_name = "vektor-ceo"
  sender_name = "affaan"
  text = "research and trade aapl"
  run_id = "run-discord-smoke-1"
  payload = @{
    symbol = "AAPL"
    side = "buy"
    quantity = 1
    price = 100
    sleeve = "tactical"
  }
} | ConvertTo-Json -Depth 8

Invoke-RestMethod -Method POST -Uri "http://localhost:8000/fund/openclaw/commands" -Headers @{ "X-OpenClaw-Token" = $token } -ContentType "application/json" -Body $body
```

Monitor workers:

```powershell
Invoke-RestMethod -Method GET -Uri "http://localhost:8000/fund/agents/workers/status"
```

Review rejected commands:

```powershell
Invoke-RestMethod -Method GET -Uri "http://localhost:8000/fund/openclaw/commands/rejections?limit=50"
```
