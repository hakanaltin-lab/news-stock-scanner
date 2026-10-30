#!/usr/bin/env bash
set -euo pipefail

AURORA_HOME="${AURORA_HOME:-$HOME/aurora}"
REPO_DIR="$AURORA_HOME/news-stock-scanner"
VENV_DIR="$AURORA_HOME/venv"
INTENT_INPUT="${1:-}"
SYMBOL="${2:-}"

fail() { printf 'FAIL: %s\n' "$*" >&2; exit 1; }

[[ -n "$INTENT_INPUT" ]] || fail "Usage: run_aurora_g4_shadow.sh INTENT_JSON SYMBOL"
[[ "$SYMBOL" =~ ^[A-Z][A-Z0-9.-]{0,9}$ ]] || fail "Invalid stock symbol."
[[ -f "$INTENT_INPUT" ]] || fail "Intent JSON not found."
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
