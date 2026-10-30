#!/usr/bin/env bash
set -euo pipefail

AURORA_HOME="${AURORA_HOME:-$HOME/aurora}"
REPO_DIR="$AURORA_HOME/news-stock-scanner"
VENV_DIR="$AURORA_HOME/venv"
INTENT_INPUT="${1:-}"
SYMBOL="${2:-}"

fail() { printf 'FAIL: %s\n' "$*" >&2; exit 1; }

[[ -n "$INTENT_INPUT" ]] || fail "Usage: run_aurora_completion_gate.sh INTENT_JSON SYMBOL"
[[ "$SYMBOL" =~ ^[A-Z][A-Z0-9.-]{0,9}$ ]] || fail "Invalid stock symbol."
[[ -f "$INTENT_INPUT" ]] || fail "Intent JSON not found."
[[ -x "$VENV_DIR/bin/python" ]] || fail "Python venv missing."
[[ -d "$REPO_DIR/.git" ]] || fail "AURORA repository missing."

INTENT_FILE="$(realpath -- "$INTENT_INPUT")"
cd "$REPO_DIR"

[[ -f runtime/gcp/latest.json ]] || fail "Sanitized G0/G1 proof missing."

echo "==> Run fresh G2/G3 and broker-independent G4 shadow gate"
bash scripts/run_aurora_g4_shadow.sh "$INTENT_FILE" "$SYMBOL"

echo "==> Audit persistent shadow ledger in read-only mode"
"$VENV_DIR/bin/python" scripts/audit_aurora_g4_ledger.py

echo "==> Evaluate final G0-G4 Paper shadow completion status"
"$VENV_DIR/bin/python" scripts/aurora_completion_status.py

echo "PASS: AURORA Paper runtime validated in shadow-only mode."
echo "Broker submission: DISABLED"
echo "Paper order submission: DISABLED"
echo "LIVE and real-money trading: DISABLED"
