#!/usr/bin/env bash
set -euo pipefail

# --- config ---
ENABLE_AT="${ENABLE_AT:-21:00}"             # change via env if you like
CMD="$HOME/.local/bin/omarchy-toggle-nightlight"  # <-- adjust if your script lives elsewhere
LOG="$HOME/.local/share/nightlight-scheduler.log"
# -------------

mkdir -p "$(dirname "$LOG")"

# helper: sleep until HH:MM (works on GNU date; has BSD fallback)
sleep_until() {
  local hhmm="$1"
  local now target

  if command -v date >/dev/null 2>&1; then
    # GNU date (Linux)
    if date -d "today $hhmm" "+%s" >/dev/null 2>&1; then
      now="$(date +%s)"
      target="$(date -d "today $hhmm" +%s)"
      [ "$target" -le "$now" ] && target="$(date -d "tomorrow $hhmm" +%s)"
    else
      # BSD/macOS fallback (shouldn’t be needed on Linux)
      now="$(date +%s)"
      target="$(date -j -f "%Y-%m-%d %H:%M" "$(date +%F) $hhmm" +%s)"
      [ "$target" -le "$now" ] && target="$(date -v+1d -j -f "%Y-%m-%d %H:%M" "$(date +%F) $hhmm" +%s)"
    fi
  fi

  local secs=$(( target - now ))
  echo "[$(date)] sleeping ${secs}s until $hhmm" >>"$LOG"
  sleep "$secs"
}

echo "[$(date)] scheduler started; will run at $ENABLE_AT daily" >>"$LOG"

# ensure hyprsunset exists (no harm if already running)
if ! pgrep -x hyprsunset >/dev/null 2>&1; then
  setsid -f hyprsunset >/dev/null 2>&1 || true
  echo "[$(date)] started hyprsunset (if not running)" >>"$LOG"
fi

while :; do
  sleep_until "$ENABLE_AT"
  echo "[$(date)] running toggle: $CMD" >>"$LOG"
  "$CMD" >>"$LOG" 2>&1 || echo "[$(date)] toggle failed ($?)" >>"$LOG"
done
