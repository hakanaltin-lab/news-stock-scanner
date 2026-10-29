#!/usr/bin/env bash
set -euo pipefail

AURORA_HOME="${AURORA_HOME:-$HOME/aurora}"
VENV_DIR="$AURORA_HOME/venv"
ZIP_PATH="${1:-}"

fail() { printf 'FAIL: %s\n' "$*" >&2; exit 1; }

[[ -n "$ZIP_PATH" ]] || fail "Usage: $0 <official-tws-api-macunix-zip>"
[[ -f "$ZIP_PATH" ]] || fail "API ZIP not found: $ZIP_PATH"
[[ -x "$VENV_DIR/bin/python" ]] || fail "Run bootstrap_aurora_g2_vps.sh first."

BASENAME="$(basename "$ZIP_PATH")"
case "$BASENAME" in
  twsapi_macunix*.zip) ;;
  *) fail "Unexpected API ZIP name. Use the official twsapi_macunix*.zip package." ;;
esac

WORKDIR="$(mktemp -d)"
trap 'rm -rf "$WORKDIR"' EXIT

unzip -q "$ZIP_PATH" -d "$WORKDIR"

SETUP_FILE="$(find "$WORKDIR" -type f -path '*/pythonclient/setup.py' -print -quit)"
if [[ -z "$SETUP_FILE" ]]; then
  SETUP_FILE="$(find "$WORKDIR" -type f -name setup.py -path '*/source/*' -print -quit)"
fi
[[ -n "$SETUP_FILE" ]] || fail "Could not locate the official Python API setup.py."

PYTHONCLIENT_DIR="$(dirname "$SETUP_FILE")"

"$VENV_DIR/bin/python" -m pip install "$PYTHONCLIENT_DIR"

"$VENV_DIR/bin/python" - <<'PY'
from ibapi.client import EClient
from ibapi.wrapper import EWrapper
print("PASS: official IBKR Python API imports successfully.")
PY

echo "Source package SHA256:"
sha256sum "$ZIP_PATH"
echo "Paper order submission: DISABLED"
echo "LIVE trading: DISABLED"
