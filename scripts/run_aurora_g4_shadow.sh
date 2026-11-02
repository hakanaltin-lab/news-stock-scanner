#!/usr/bin/env bash
set -euo pipefail

AURORA_HOME="${AURORA_HOME:-$HOME/aurora}"
REPO_DIR="$AURORA_HOME/news-stock-scanner"
VENV_DIR="$AURORA_HOME/venv"
INTENT_INPUT="${1:-}"
SYMBOL="${2:-}"

fail() { printf 'FAIL: %s\n' "$*" >&2; exit 1; }

[[ "$(id -u)" -ne 0 ]] || fail "Run as the normal OS Login user, not root."
[[ -n "$INTENT_INPUT" ]] || fail "Usage: run_aurora_g4_shadow.sh INTENT_JSON SYMBOL"
[[ "$SYMBOL" =~ ^[A-Z][A-Z0-9.-]{0,9}$ ]] || fail "Invalid stock symbol."
[[ -f "$INTENT_INPUT" && ! -L "$INTENT_INPUT" ]] || fail "Intent JSON must be a regular non-symlink file."
[[ "$(stat -c %u "$INTENT_INPUT")" == "$(id -u)" ]] || fail "Intent JSON owner is invalid."
[[ "$(stat -c %a "$INTENT_INPUT")" == "600" ]] || fail "Intent JSON mode must be 600."
[[ "$(stat -c %h "$INTENT_INPUT")" == "1" ]] || fail "Intent JSON hard links are forbidden."
[[ -x "$VENV_DIR/bin/python" ]] || fail "Python venv missing."
[[ -d "$REPO_DIR/.git" ]] || fail "AURORA repository missing."

INTENT_FILE="$(realpath -- "$INTENT_INPUT")"
cd "$REPO_DIR"

echo "==> Refresh G2/G3 runtime evidence"
bash scripts/run_aurora_g2_g3_readiness.sh "$SYMBOL"

echo "==> Create audited G4 shadow order"
AURORA_RUN_MODE=DRY_RUN \
  "$VENV_DIR/bin/python" scripts/aurora_g4_shadow.py \
  --intent "$INTENT_FILE"

echo "PASS: G4 shadow order accepted for operator review."
echo "Broker submission: DISABLED"
echo "Paper order submission: DISABLED"
echo "LIVE trading: DISABLED"
