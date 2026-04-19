#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="${1:-$HOME/Vektor}"
BACKUP_ROOT="${2:-$HOME/vektor-backups}"
KEEP_DAYS="${KEEP_DAYS:-14}"

BACKEND_DIR="$REPO_DIR/backend"
KNOWLEDGE_DIR="$REPO_DIR/knowledge_graph"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
TARGET_DIR="$BACKUP_ROOT/$STAMP"

mkdir -p "$TARGET_DIR"

copy_if_exists() {
  local src="$1"
  local dst="$2"
  if [[ -e "$src" ]]; then
    mkdir -p "$(dirname "$dst")"
    cp -a "$src" "$dst"
  fi
}

copy_if_exists "$BACKEND_DIR/trading_bot.db" "$TARGET_DIR/trading_bot.db"
copy_if_exists "$BACKEND_DIR/trading_bot.db-wal" "$TARGET_DIR/trading_bot.db-wal"
copy_if_exists "$BACKEND_DIR/trading_bot.db-shm" "$TARGET_DIR/trading_bot.db-shm"
copy_if_exists "$BACKEND_DIR/.env" "$TARGET_DIR/backend.env"

if [[ -d "$KNOWLEDGE_DIR" ]]; then
  rsync -a --delete "$KNOWLEDGE_DIR/" "$TARGET_DIR/knowledge_graph/"
fi

tar -C "$BACKUP_ROOT" -czf "$BACKUP_ROOT/vektor-backup-$STAMP.tar.gz" "$STAMP"
rm -rf "$TARGET_DIR"

find "$BACKUP_ROOT" -type f -name "vektor-backup-*.tar.gz" -mtime "+$KEEP_DAYS" -delete

echo "Backup completed: $BACKUP_ROOT/vektor-backup-$STAMP.tar.gz"
