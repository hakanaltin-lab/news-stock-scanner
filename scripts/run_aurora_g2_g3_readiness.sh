#!/usr/bin/env bash
set -euo pipefail

AURORA_HOME="${AURORA_HOME:-$HOME/aurora}"
REPO_DIR="$AURORA_HOME/news-stock-scanner"
VENV_DIR="$AURORA_HOME/venv"
ENV_FILE="$HOME/.config/aurora/ibkr-paper.env"
SYMBOL="${1:-BKR}"

fail() { printf 'FAIL: %s\n' "$*" >&2; exit 1; }

[[ "$SYMBOL" =~ ^[A-Z][A-Z0-9.-]{0,9}$ ]] || fail "Invalid stock symbol."
[[ -f "$ENV_FILE" ]] || fail "Runtime env missing."
[[ -x "$VENV_DIR/bin/python" ]] || fail "Python venv missing."
[[ -d "$REPO_DIR/.git" ]] || fail "AURORA repository missing."

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

[[ "${AURORA_RUN_MODE:-}" == "READ_ONLY" ]] || fail "AURORA_RUN_MODE must be READ_ONLY."
[[ "${AURORA_IBKR_MODE:-}" == "PAPER" ]] || fail "IBKR mode must be PAPER."
[[ "${AURORA_IBKR_HOST:-}" == "127.0.0.1" ]] || fail "IBKR host must be loopback."
[[ "${AURORA_IBKR_PORT:-}" == "4002" ]] || fail "IBKR Paper port must be 4002."

cd "$REPO_DIR"

readonly AURORA_EVIDENCE_RUN_ID="$(
  "$VENV_DIR/bin/python" -c 'import uuid; print(uuid.uuid4())'
)"
export AURORA_EVIDENCE_RUN_ID

echo "==> G2 Paper Read-Only proof"
g2_status=0
bash scripts/run_aurora_g2_readonly.sh || g2_status=$?

echo "==> G3 verified real-time market-data proof for $SYMBOL"
export AURORA_IBKR_MARKET_DATA_ENABLED=true
g3_status=0
"$VENV_DIR/bin/python" scripts/ibkr_market_data_probe.py "$SYMBOL" || g3_status=$?

echo "==> Unified fail-closed readiness decision"
summary_status=0
"$VENV_DIR/bin/python" scripts/aurora_readiness_summary.py || summary_status=$?

if (( g2_status != 0 || g3_status != 0 || summary_status != 0 )); then
  printf 'FAIL: G2 status=%d, G3 status=%d, summary status=%d.\n' \
    "$g2_status" "$g3_status" "$summary_status" >&2
  echo "Paper order submission: DISABLED"
  echo "LIVE trading: DISABLED"
  exit 2
fi

echo "PASS: Fresh G2/G3 evidence is ready for controlled G4 dry-run."
echo "Paper order submission: DISABLED"
echo "LIVE trading: DISABLED"
