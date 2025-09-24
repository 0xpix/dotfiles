#!/usr/bin/env bash
set -euo pipefail

# Optional: also disable at a morning time (set to empty to skip)
DISABLE_AT="07:00"   # e.g. "07:00" or "" to skip
ENABLE_AT="21:40"    # your requested 17:00

# Path to your existing toggle (don’t modify it)
TOGGLE_BIN="${HOME}/.local/bin/omarchy-toggle-nightlight"

# Helper: sleep until a given HH:MM in local time
sleep_until() {
  local hhmm="$1"
  # Today’s target
  local target="$(date -d "today ${hhmm}" +%s 2>/dev/null || date -j -f "%Y-%m-%d %H:%M" "$(date +%F) ${hhmm}" +%s)"
  local now="$(date +%s)"
  # If the time already passed today, use tomorrow
  if [ "$target" -le "$now" ]; then
    target="$(date -d "tomorrow ${hhmm}" +%s 2>/dev/null || date -j -v+1d -f "%Y-%m-%d %H:%M" "$(date +%F) ${hhmm}" +%s)"
  fi
  sleep $(( target - now ))
}

# Make sure hyprsunset is running, like your toggle does
if ! pgrep -x hyprsunset >/dev/null 2>&1; then
  setsid uwsm app -- hyprsunset >/dev/null 2>&1 &
  sleep 1
fi

while :; do
  # Morning disable (optional)
  if [ -n "${DISABLE_AT}" ]; then
    sleep_until "${DISABLE_AT}"
    # Ensure it's OFF/daylight after morning time
    hyprctl hyprsunset temperature 6000 >/dev/null 2>&1 || true
  fi

  # Evening enable
  sleep_until "${ENABLE_AT}"
  # Use your existing toggle helper (kept unmodified)
  "${TOGGLE_BIN}" >/dev/null 2>&1 || true

  # Loop to next day
done
