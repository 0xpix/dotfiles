#!/usr/bin/env bash
set -euo pipefail

# Consider temps >= OFF_TEMP as "OFF/daylight"
OFF_TEMP="${NIGHTLIGHT_OFF_TEMP:-6000}"

get_temp() {
  # Try JSON first (newer Hyprland). Parse without jq.
  if out="$(hyprctl -j hyprsunset 2>/dev/null)"; then
    # If JSON says running:false -> off
    if echo "$out" | grep -q '"running"[[:space:]]*:[[:space:]]*false'; then
      echo 0; return
    fi
    # Extract "temperature": <num>
    t="$(echo "$out" | grep -oE '"temperature"[[:space:]]*:[[:space:]]*[0-9]+' \
         | grep -oE '[0-9]+' || true)"
    if [ -n "${t:-}" ]; then echo "$t"; return; fi
  fi

  # Fallback: text mode
  if out="$(hyprctl hyprsunset 2>/dev/null)"; then
    # If text says disabled -> off
    if echo "$out" | grep -qi 'disable'; then
      echo 0; return
    fi
    # Try explicit "temperature" subcommand
    if tline="$(hyprctl hyprsunset temperature 2>/dev/null || true)"; then
      t="$(echo "$tline" | grep -oE '[0-9]{3,5}' | head -n1 || true)"
      [ -n "${t:-}" ] && { echo "$t"; return; }
    fi
    # Otherwise grab any number like "3500K" from generic output
    t="$(echo "$out" | grep -oE '[0-9]{3,5}' | head -n1 || true)"
    [ -n "${t:-}" ] && { echo "$t"; return; }
  fi

  # If everything failed, assume off
  echo 0
}

temp="$(get_temp)"

# Active when 0 < temp < OFF_TEMP; otherwise OFF
if [ "$temp" -gt 0 ] && [ "$temp" -lt "$OFF_TEMP" ]; then
  icon=""   # sun = nightlight active (warm)
  text="${temp}K"
  cls="active"
  tip="Nightlight: ${temp}K"
else
  icon=""   # moon = off/daylight
  text="OFF"
  cls="inactive"
  tip="Nightlight: off"
fi

printf '{"text":"%s %s","tooltip":"%s","class":"%s"}\n' "$icon" "$text" "$tip" "$cls"
