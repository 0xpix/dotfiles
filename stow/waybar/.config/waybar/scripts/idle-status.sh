#!/usr/bin/env bash
set -euo pipefail

# quick process check
is_running() { pgrep -x hypridle >/dev/null 2>&1; }

# First read
state="$(is_running && echo idle || echo active)"

# Short settle loop (up to ~0.6s) to catch just-triggered flips
# This helps when exec-on-event runs before hypridle actually starts/stops.
for _ in 1 2 3 4 5 6; do
  sleep 0.1
  now="$(is_running && echo idle || echo active)"
  if [[ "$now" != "$state" ]]; then
    state="$now"
    break
  fi
done

if [[ "$state" == "idle" ]]; then
  icon="💤"; text="ON";  cls="idle";   alt="idle";   tip="Idle lock: enabled"
else
  icon="⚡"; text="OFF"; cls="active"; alt="active"; tip="Idle lock: disabled"
fi

# Emit both class and alt; Waybar uses either for {icon} mapping depending on build
printf '{"text":"%s %s","tooltip":"%s","class":"%s","alt":"%s"}\n' \
       "$icon" "$text" "$tip" "$cls" "$alt"
