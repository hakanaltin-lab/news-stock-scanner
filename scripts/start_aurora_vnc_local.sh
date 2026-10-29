#!/usr/bin/env bash
set -euo pipefail

DISPLAY_NUMBER="${AURORA_VNC_DISPLAY:-2}"
GEOMETRY="${AURORA_VNC_GEOMETRY:-1600x900}"
PORT="$((5900 + DISPLAY_NUMBER))"

fail() { printf 'FAIL: %s\n' "$*" >&2; exit 1; }

[[ -f "$HOME/.vnc/passwd" ]] || fail "Run vncpasswd first."

if ss -lntH | awk -v p=":$PORT" '
  $4 ~ p"$" && (
    $4 ~ /^0\.0\.0\.0:/ ||
    $4 ~ /^\[::\]:/ ||
    $4 ~ /^\*:/
  ) {found=1}
  END {exit !found}
'; then
  fail "TCP/$PORT is already publicly bound."
fi

vncserver -kill ":$DISPLAY_NUMBER" >/dev/null 2>&1 || true

vncserver ":$DISPLAY_NUMBER" \
  -localhost yes \
  -geometry "$GEOMETRY" \
  -depth 24

sleep 1

if ! ss -lntH | grep -Eq "(127\.0\.0\.1|\[::1\]):$PORT([[:space:]]|$)"; then
  fail "Expected localhost-only VNC listener on TCP/$PORT was not found."
fi

if ss -lntH | awk -v p=":$PORT" '
  $4 ~ p"$" && (
    $4 ~ /^0\.0\.0\.0:/ ||
    $4 ~ /^\[::\]:/ ||
    $4 ~ /^\*:/
  ) {found=1}
  END {exit !found}
'; then
  fail "VNC unexpectedly exposed TCP/$PORT publicly."
fi

cat <<EOF

PASS: VNC display :$DISPLAY_NUMBER is localhost-only on TCP/$PORT.

Connect through the existing IAP SSH path with local forwarding.
Do not create a public firewall rule for TCP/$PORT.
EOF
