#!/usr/bin/env bash
set -euo pipefail

: "${DATABASE_URL:?DATABASE_URL is required}"
BACKUP_DIR="${BACKUP_DIR:-./backups}"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-14}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$BACKUP_DIR"

pg_dump "$DATABASE_URL" --format=custom --no-owner --no-acl \
  --file="$BACKUP_DIR/research-ai-$STAMP.dump"

find "$BACKUP_DIR" -type f -name 'research-ai-*.dump' \
  -mtime "+$RETENTION_DAYS" -delete

echo "Backup written to $BACKUP_DIR/research-ai-$STAMP.dump"
