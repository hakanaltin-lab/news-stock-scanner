#!/usr/bin/env bash
set -euo pipefail

DISPLAY_NUMBER="${AURORA_VNC_DISPLAY:-2}"
export DISPLAY=":${DISPLAY_NUMBER}"

fail() { printf 'FAIL: %s\n' "$*" >&2; exit 1; }

if ! ss -lntH | grep -Eq "(127\.0\.0\.1|\[::1\]):$((5900 + DISPLAY_NUMBER))([[:space:]]|$)"; then
  fail "Local VNC display :$DISPLAY_NUMBER is not running."
fi

LAUNCHER="$(
  find "$HOME/Jts" "$HOME" \
    -maxdepth 6 \
    -type f \
    -name ibgateway \
    -perm -u+x \
    2>/dev/null \
    | head -n1
)"

[[ -n "$LAUNCHER" ]] || fail "IB Gateway launcher not found. Install IB Gateway first."

nohup "$LAUNCHER" >"$HOME/.ibgateway-aurora.log" 2>&1 &

echo "IB Gateway launch requested on DISPLAY=$DISPLAY."
echo "Complete the PAPER login manually in the VNC session."
echo "Log: $HOME/.ibgateway-aurora.log"
