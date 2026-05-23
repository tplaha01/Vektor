#!/usr/bin/env bash
set -euo pipefail

DB_NAME="${1:-vektor}"
DB_USER="${2:-vektor}"
DB_PASSWORD="${3:?database password required}"

echo "[postgres] Installing PostgreSQL..."
sudo apt-get update -y
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y postgresql postgresql-contrib
sudo systemctl enable --now postgresql

echo "[postgres] Creating role/database..."
sudo -u postgres psql -v ON_ERROR_STOP=1 <<SQL
DO \$\$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = '${DB_USER}') THEN
    CREATE ROLE ${DB_USER} LOGIN PASSWORD '${DB_PASSWORD}';
  ELSE
    ALTER ROLE ${DB_USER} WITH LOGIN PASSWORD '${DB_PASSWORD}';
  END IF;
END
\$\$;
SELECT 'CREATE DATABASE ${DB_NAME} OWNER ${DB_USER}'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '${DB_NAME}')\gexec
GRANT ALL PRIVILEGES ON DATABASE ${DB_NAME} TO ${DB_USER};
SQL

echo "[postgres] Restricting Postgres to local host..."
PG_VERSION="$(ls /etc/postgresql | sort -V | tail -1)"
CONF="/etc/postgresql/${PG_VERSION}/main/postgresql.conf"
HBA="/etc/postgresql/${PG_VERSION}/main/pg_hba.conf"
sudo sed -i "s/^#\?listen_addresses.*/listen_addresses = '127.0.0.1'/" "$CONF"
if ! sudo grep -q "127.0.0.1/32 scram-sha-256" "$HBA"; then
  echo "host    all             all             127.0.0.1/32            scram-sha-256" | sudo tee -a "$HBA" >/dev/null
fi
sudo systemctl restart postgresql
echo "[postgres] Ready on 127.0.0.1:5432/${DB_NAME}"
