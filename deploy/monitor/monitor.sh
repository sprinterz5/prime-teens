#!/usr/bin/env bash
# PrimeTeens - lightweight self-healing monitor. Runs every minute via
# primeteens-monitor.timer. Policy (see deploy/README.md for the long
# version):
#   - self-heal silently: a check failing 3 runs in a row -> restart that
#     unit, at most once per unit per 10 minutes.
#   - alert on Telegram only on state transitions: a problem still present
#     5 minutes after it started (i.e. after the restart attempt already had
#     a chance to fix it) -> one message. Recovery -> one message. Disk,
#     backup-age and archive-job alerts at most once per 24h each. No "all
#     ok" spam.
#   - if MONITOR_BOT_TOKEN/MONITOR_CHAT_ID are not configured, just log to
#     journald instead of trying to send anything.
set -euo pipefail

STATE_DIR="/var/lib/primeteens-monitor"
ENV_FILE="/etc/primeteens/monitor.env"
BACKUP_ROOT="/var/backups/primeteens"

UNITS=("primeteens-web" "primeteens-mentor" "primeteens-kids")
HEALTH_URL="http://127.0.0.1:3000/api/health"
DISK_PATH="/"
DISK_THRESHOLD=85          # percent
BACKUP_MAX_AGE_HOURS=26
FAIL_THRESHOLD=3           # consecutive failing runs before we self-heal
ALERT_AFTER_SECONDS=300    # 5 min of *continued* trouble before we alert
RESTART_COOLDOWN_SECONDS=600  # 10 min between auto-restarts of the same unit
DAILY_ALERT_SECONDS=86400     # disk / backup alerts at most once per 24h

mkdir -p "$STATE_DIR"
if [[ -r "$ENV_FILE" ]]; then
  # shellcheck disable=SC1090
  source "$ENV_FILE"
fi

now=$(date +%s)

log() { logger -t primeteens-monitor "$*" 2>/dev/null || echo "[primeteens-monitor] $*"; }

send_telegram() {
  local text="$1"
  if [[ -z "${MONITOR_BOT_TOKEN:-}" || -z "${MONITOR_CHAT_ID:-}" ]]; then
    log "(no MONITOR_BOT_TOKEN/MONITOR_CHAT_ID configured) $text"
    return 0
  fi
  curl -fsS --max-time 10 \
    -X POST "https://api.telegram.org/bot${MONITOR_BOT_TOKEN}/sendMessage" \
    --data-urlencode "chat_id=${MONITOR_CHAT_ID}" \
    --data-urlencode "text=${text}" \
    >/dev/null || log "failed to send Telegram alert: $text"
}

# --- tiny key=value state store, one file per check -------------------------
# Fields: fail_count, problem_since (epoch, 0 = no ongoing problem),
# alerted (1/0), last_restart (epoch), last_daily_alert (epoch).
state_file() { echo "$STATE_DIR/$1.state"; }

read_state() {
  local file; file=$(state_file "$1")
  fail_count=0; problem_since=0; alerted=0; last_restart=0; last_daily_alert=0
  if [[ -f "$file" ]]; then
    # shellcheck disable=SC1090
    source "$file"
  fi
}

write_state() {
  local file; file=$(state_file "$1")
  cat > "$file" <<EOF
fail_count=$fail_count
problem_since=$problem_since
alerted=$alerted
last_restart=$last_restart
last_daily_alert=$last_daily_alert
EOF
}

# Record a check result, self-heal after FAIL_THRESHOLD, alert on the
# transition to "still broken after ALERT_AFTER_SECONDS", alert once on
# recovery. `restart_cmd`, if non-empty, is what self-heals this check.
handle_check() {
  local name="$1" ok="$2" restart_cmd="${3:-}" human="${4:-$1}"
  read_state "$name"

  if [[ "$ok" == "true" ]]; then
    if (( alerted == 1 )); then
      local down_min=$(( (now - problem_since) / 60 ))
      send_telegram "✅ восстановилось, лежало ${down_min} мин: ${human}"
    fi
    fail_count=0; problem_since=0; alerted=0
    write_state "$name"
    return
  fi

  fail_count=$((fail_count + 1))
  if (( problem_since == 0 )); then
    problem_since=$now
  fi

  if (( fail_count == FAIL_THRESHOLD )) && [[ -n "$restart_cmd" ]]; then
    if (( now - last_restart >= RESTART_COOLDOWN_SECONDS )); then
      log "self-healing: $human ($restart_cmd)"
      eval "$restart_cmd" || true
      last_restart=$now
    else
      log "skip restart for $human, cooldown active"
    fi
  fi

  if (( alerted == 0 )) && (( now - problem_since >= ALERT_AFTER_SECONDS )); then
    send_telegram "⚠️ проблема: ${human}, не проходит уже $(( (now - problem_since) / 60 )) мин"
    alerted=1
  fi

  write_state "$name"
}

# A simpler variant for disk/backup: no self-heal, alert at most once/24h
# while the condition persists, single recovery message.
handle_daily_check() {
  local name="$1" ok="$2" human="${3:-$1}"
  read_state "$name"

  if [[ "$ok" == "true" ]]; then
    if (( alerted == 1 )); then
      send_telegram "✅ восстановилось: ${human}"
    fi
    fail_count=0; problem_since=0; alerted=0; last_daily_alert=0
    write_state "$name"
    return
  fi

  if (( problem_since == 0 )); then
    problem_since=$now
  fi

  if (( now - last_daily_alert >= DAILY_ALERT_SECONDS )); then
    send_telegram "⚠️ ${human}"
    alerted=1
    last_daily_alert=$now
  fi

  write_state "$name"
}

# --- 1. HTTP health check ----------------------------------------------------
health_ok=true
curl -fsS --max-time 5 "$HEALTH_URL" >/dev/null 2>&1 || health_ok=false
handle_check "http_health" "$health_ok" "systemctl restart primeteens-web" "сайт не отвечает ($HEALTH_URL)"

# --- 2. systemd units ---------------------------------------------------------
for unit in "${UNITS[@]}"; do
  unit_ok=true
  systemctl is-active --quiet "$unit" || unit_ok=false
  handle_check "unit_${unit}" "$unit_ok" "systemctl restart ${unit}" "сервис ${unit} не запущен"
done

# --- 3. disk usage -------------------------------------------------------------
disk_used=$(df -P "$DISK_PATH" | awk 'NR==2 {gsub("%","",$5); print $5}') || true
disk_ok=true
if [[ -n "$disk_used" ]] && (( disk_used >= DISK_THRESHOLD )); then
  disk_ok=false
fi
handle_daily_check "disk" "$disk_ok" "диск заполнен на ${disk_used:-?}% (порог ${DISK_THRESHOLD}%)"

# --- 4. last backup age --------------------------------------------------------
backup_ok=true
if [[ -d "$BACKUP_ROOT" ]]; then
  newest=$(find "$BACKUP_ROOT" -maxdepth 1 -mindepth 1 -type d -printf '%T@\n' 2>/dev/null | sort -n | tail -1) || true
  if [[ -z "$newest" ]]; then
    backup_ok=false
  else
    age_hours=$(( (now - ${newest%.*}) / 3600 ))
    if (( age_hours > BACKUP_MAX_AGE_HOURS )); then
      backup_ok=false
    fi
  fi
else
  backup_ok=false
fi
handle_daily_check "backup" "$backup_ok" "нет свежего бэкапа (старше ${BACKUP_MAX_AGE_HOURS}ч) в ${BACKUP_ROOT}"

# --- 5. nightly archive job (last run) -----------------------------------------
# `systemctl is-failed` on a oneshot unit reflects the last run triggered by
# its timer: "failed" until the next successful run resets it, "inactive"
# otherwise. No self-heal here (nothing to restart, it already ran and
# failed) - same once-per-24h alert policy as disk/backup.
archive_ok=true
if systemctl is-failed --quiet primeteens-archive.service; then
  archive_ok=false
fi
handle_daily_check "archive" "$archive_ok" "ночной archive:pending упал (primeteens-archive.service в состоянии failed)"

exit 0
