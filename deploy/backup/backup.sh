#!/usr/bin/env bash
# PrimeTeens - daily backup: Postgres dump + storage/ + bot/data, with
# retention (7 daily + 4 weekly) and an optional off-site copy.
#
# storage/ is archived whole (recursively), so this also picks up
# storage/archive/ (group PDF exports) alongside storage/drawings/ - nothing
# extra to configure when new subdirectories are added under storage/.
#
# Run as root (or a user allowed to read /opt/prime-teens/.env and the
# Postgres role used by DATABASE_URL). Intended to run via
# primeteens-backup.timer, but safe to run by hand too:
#   sudo /opt/prime-teens/deploy/backup/backup.sh
set -euo pipefail

APP_DIR="/opt/prime-teens"
BOT_DIR="$APP_DIR/bot"
ENV_FILE="$APP_DIR/.env"
BACKUP_ROOT="/var/backups/primeteens"
RETAIN_DAILY_DAYS=7
RETAIN_WEEKLY_DAYS=28   # Sunday backups only, kept longer

log() { echo "[$(date '+%F %T')] $*"; }
fail() { echo "[$(date '+%F %T')] ERROR: $*" >&2; exit 1; }

[[ -r "$ENV_FILE" ]] || fail "cannot read $ENV_FILE"

# Pull DATABASE_URL out of .env without sourcing the whole file (it may
# contain other values we don't want evaluated as shell).
DATABASE_URL=$(grep -E '^DATABASE_URL=' "$ENV_FILE" | tail -n1 | cut -d'=' -f2-)
DATABASE_URL=${DATABASE_URL%\"}
DATABASE_URL=${DATABASE_URL#\"}
[[ -n "$DATABASE_URL" ]] || fail "DATABASE_URL not found in $ENV_FILE"

DATE=$(date +%F)
DEST="$BACKUP_ROOT/$DATE"
mkdir -p "$DEST"

log "backing up Postgres -> $DEST/db.dump"
pg_dump -Fc "$DATABASE_URL" -f "$DEST/db.dump.tmp"
mv "$DEST/db.dump.tmp" "$DEST/db.dump"

if [[ -d "$APP_DIR/storage" ]]; then
  log "archiving storage/ (drawings + archive PDFs) -> $DEST/storage.tar.gz"
  tar -czf "$DEST/storage.tar.gz.tmp" -C "$APP_DIR" storage
  mv "$DEST/storage.tar.gz.tmp" "$DEST/storage.tar.gz"
else
  log "no storage/ dir, skipping"
fi

if [[ -d "$BOT_DIR/data" ]]; then
  log "archiving bot/data -> $DEST/bot-data.tar.gz"
  tar -czf "$DEST/bot-data.tar.gz.tmp" -C "$BOT_DIR" data
  mv "$DEST/bot-data.tar.gz.tmp" "$DEST/bot-data.tar.gz"
else
  log "no bot/data dir, skipping"
fi

log "local backup OK: $DEST"

# --- retention: keep 7 most recent daily dirs + Sunday dirs up to 28 days ---
log "applying retention (7 daily / 4 weekly)"
now_epoch=$(date +%s)
for dir in "$BACKUP_ROOT"/*/; do
  dir=${dir%/}
  name=$(basename "$dir")
  [[ "$name" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]] || continue

  dir_epoch=$(date -d "$name" +%s 2>/dev/null) || continue
  age_days=$(( (now_epoch - dir_epoch) / 86400 ))
  weekday=$(date -d "$name" +%u)  # 1=Mon .. 7=Sun

  if (( age_days <= RETAIN_DAILY_DAYS )); then
    continue  # within daily retention window, always keep
  fi
  if [[ "$weekday" == "7" ]] && (( age_days <= RETAIN_WEEKLY_DAYS )); then
    continue  # Sunday backup, still within weekly retention window
  fi

  log "pruning old backup $dir (age ${age_days}d)"
  rm -rf "$dir"
done

# --- optional off-site copy (age-encrypted) ---------------------------------
if [[ -n "${BACKUP_REMOTE:-}" ]]; then
  [[ -n "${BACKUP_AGE_RECIPIENT:-}" ]] || fail "BACKUP_REMOTE is set but BACKUP_AGE_RECIPIENT is not"
  command -v age >/dev/null || fail "BACKUP_REMOTE is set but 'age' is not installed"

  log "encrypting backup for off-site copy"
  ARCHIVE="$BACKUP_ROOT/$DATE.tar"
  tar -cf "$ARCHIVE" -C "$BACKUP_ROOT" "$DATE"
  age -r "$BACKUP_AGE_RECIPIENT" -o "$ARCHIVE.age" "$ARCHIVE"
  rm -f "$ARCHIVE"

  log "copying $ARCHIVE.age -> $BACKUP_REMOTE"
  if [[ "$BACKUP_REMOTE" == *:* ]]; then
    scp -q "$ARCHIVE.age" "$BACKUP_REMOTE/"
  else
    fail "BACKUP_REMOTE must look like user@host:/path"
  fi
  rm -f "$ARCHIVE.age"
  log "off-site copy done"
else
  log "BACKUP_REMOTE not set, skipping off-site copy (local backup only)"
fi

log "backup finished successfully"
