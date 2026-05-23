# Move Vektor to AWS us-west-2 with Hosted Postgres

Phoenix is closest to AWS `us-west-2` among standard AWS regions. AWS does not
have a normal region named `us-west-23`; use `us-west-2` unless a specific
Local Zone is later configured.

## Current Live State

The live recovery deployment on May 17, 2026 uses the west-coast backend VM with
self-hosted PostgreSQL because the available AWS IAM user was denied RDS subnet
group discovery.

```text
AWS account: 735115318411
Region: us-west-2
Backend instance: i-0b1e12d7dc35041fc
West API host: https://35.84.237.249.sslip.io
Storage: DB_BACKEND=postgres on local VM PostgreSQL
Postgres bind address: 127.0.0.1
```

The previous east-coast HTTPS host remains usable as a compatibility proxy:

```text
https://35.168.170.143.sslip.io -> https://35.84.237.249.sslip.io
```

That means an existing Vercel deployment that still points to the east
`sslip.io` URL can keep working until Vercel credentials are available and
`VITE_BACKEND_URL` is updated to the west host.

The live migration copied `29` tables and `207038` rows from the preserved
SQLite database into PostgreSQL. The east backend service was stopped to avoid
duplicate Alpaca websocket connections; east Caddy remains active only as the
proxy.

This migration has two separate moves:

1. Create hosted Postgres in `us-west-2`.
2. Move the backend VM to `us-west-2`.

The safe order is Postgres first, then VM. That preserves the current SQLite
data before any backend traffic is moved.

## Local Prerequisites

Use AWS credentials that can create EC2, security groups, Elastic IPs, and RDS
in `us-west-2`.

```powershell
$env:AWS_ACCESS_KEY_ID="<key>"
$env:AWS_SECRET_ACCESS_KEY="<secret>"
$env:AWS_DEFAULT_REGION="us-west-2"
```

The existing private key can be reused by importing its public key into the
`us-west-2` EC2 key-pair registry:

```text
$HOME\.ssh\vektor-aws-us-east-1.pem
```

## 1. Create Postgres

Preferred managed option, if IAM allows RDS:

```powershell
py -3 scripts\aws\provision_us_west_postgres.py --region us-west-2 --wait
```

This writes:

```text
.run/aws-us-west-2-postgres.json
```

Use its `database_url` as the backend `DATABASE_URL`. The RDS instance is not
publicly exposed; it allows port `5432` only from the Vektor backend security
group.

Fallback used by the live deployment when RDS IAM permissions are unavailable:

```powershell
scp -i "$HOME\.ssh\vektor-aws-us-east-1.pem" `
  scripts\aws\setup_vm_postgres.sh `
  ubuntu@35.84.237.249:/tmp/setup_vm_postgres.sh

ssh -i "$HOME\.ssh\vektor-aws-us-east-1.pem" ubuntu@35.84.237.249 `
  "bash /tmp/setup_vm_postgres.sh vektor vektor '<strong-password>'"
```

Use a local-only database URL in the backend env:

```env
DB_BACKEND=postgres
DATABASE_URL=postgresql://vektor:<strong-password>@127.0.0.1:5432/vektor
```

## 2. Migrate Existing SQLite into Postgres

Run this against the currently live backend VM first. It backs up
`backend/trading_bot.db`, installs the Postgres driver, creates the Postgres
schema, copies all SQLite tables, and switches that backend to `DB_BACKEND=postgres`.

```powershell
$pg = (Get-Content .run\aws-us-west-2-postgres.json | ConvertFrom-Json).database_url

.\scripts\aws\switch_backend_to_postgres.ps1 `
  -VmHost "35.168.170.143" `
  -User "ubuntu" `
  -KeyPath "$HOME\.ssh\vektor-aws-us-east-1.pem" `
  -RepoDir "/home/ubuntu/Vektor" `
  -DatabaseUrl $pg
```

If you only want to copy data and not restart the east-coast backend into
Postgres yet, add `-MigrateOnly`.

## 3. Create the us-west-2 Backend VM

```powershell
py -3 scripts\aws\provision_us_west_backend_vm.py `
  --region us-west-2 `
  --private-key-path "$HOME\.ssh\vektor-aws-us-east-1.pem"
```

This writes:

```text
.run/aws-us-west-2-backend-vm.json
```

## 4. Deploy Backend to us-west-2

Export the existing production env from the current VM, then add the Postgres
settings. Do not commit this env file.

```powershell
$west = Get-Content .run\aws-us-west-2-backend-vm.json | ConvertFrom-Json
$pg = (Get-Content .run\aws-us-west-2-postgres.json | ConvertFrom-Json).database_url

scp -i "$HOME\.ssh\vektor-aws-us-east-1.pem" `
  ubuntu@35.168.170.143:/home/ubuntu/Vektor/backend/.env `
  .run\backend-west.env

Add-Content .run\backend-west.env "DB_BACKEND=postgres"
Add-Content .run\backend-west.env "DATABASE_URL=$pg"

.\scripts\aws\deploy_aws_backend.ps1 `
  -VmHost $west.public_ip `
  -User "ubuntu" `
  -KeyPath "$HOME\.ssh\vektor-aws-us-east-1.pem" `
  -RepoUrl "https://github.com/tplaha01/Vektor.git" `
  -RepoDir "/home/ubuntu/Vektor" `
  -Branch "main" `
  -UseSslipHost `
  -UploadEnv `
  -LocalEnvPath ".run\backend-west.env"
```

The temporary HTTPS backend will be:

```text
https://<west-elastic-ip>.sslip.io
```

Set Vercel:

```env
VITE_BACKEND_URL=https://35.84.237.249.sslip.io
VITE_API_KEY=<same backend API_KEY>
```

Then redeploy the Vercel frontend.

## 5. Verify

```powershell
Invoke-WebRequest "https://<west-elastic-ip>.sslip.io/health" -UseBasicParsing

$headers = @{
  Origin = "https://vektor-kappa.vercel.app"
  "X-API-Key" = "<backend API_KEY>"
}
Invoke-WebRequest "https://<west-elastic-ip>.sslip.io/api/admin/metrics/summary" -Headers $headers -UseBasicParsing
```

On the VM:

```bash
sudo systemctl status vektor-backend --no-pager
sudo journalctl -u vektor-backend -f
```

The original SQLite file remains backed up on the source VM under:

```text
/home/ubuntu/Vektor/.run/trading_bot.<timestamp>.sqlite.backup
```
