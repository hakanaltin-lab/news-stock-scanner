#!/usr/bin/env bash
set -euo pipefail

AURORA_HOME="${AURORA_HOME:-$HOME/aurora}"
REPO_DIR="$AURORA_HOME/news-stock-scanner"
VENV_DIR="$AURORA_HOME/venv"
ENV_FILE="$HOME/.config/aurora/ibkr-paper.env"

fail() { printf 'FAIL: %s\n' "$*" >&2; exit 1; }

[[ -f "$ENV_FILE" ]] || fail "Runtime env missing. Run configure_aurora_g2_runtime.sh."
[[ -x "$VENV_DIR/bin/python" ]] || fail "Python venv missing."
[[ -d "$REPO_DIR/.git" ]] || fail "AURORA repository missing."

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

[[ "${AURORA_RUN_MODE:-}" == "READ_ONLY" ]] || fail "AURORA_RUN_MODE must be READ_ONLY."
[[ "${AURORA_IBKR_ENABLED:-}" == "true" ]] || fail "AURORA_IBKR_ENABLED must be true."
[[ "${AURORA_IBKR_MODE:-}" == "PAPER" ]] || fail "AURORA_IBKR_MODE must be PAPER."
[[ "${AURORA_IBKR_HOST:-}" == "127.0.0.1" ]] || fail "IBKR host must be 127.0.0.1."
[[ "${AURORA_IBKR_PORT:-}" == "4002" ]] || fail "IBKR Paper port must be 4002."
[[ -n "${AURORA_IBKR_PAPER_ACCOUNT_ALLOWLIST:-}" ]] || fail "Paper account allowlist is missing."
[[ "${AURORA_IBKR_PAPER_ACCOUNT_ALLOWLIST}" != "DUXXXXXXX" ]] || fail "Placeholder account ID is not allowed."

if ss -lntH | awk '
  $4 ~ /:4002$/ && (
    $4 ~ /^0\.0\.0\.0:/ ||
    $4 ~ /^\[::\]:/ ||
    $4 ~ /^\*:/
  ) {found=1}
  END {exit !found}
'; then
  fail "IBKR TCP/4002 is publicly bound."
fi

if ! ss -lntH | grep -Eq "(127\.0\.0\.1|\[::1\]):4002([[:space:]]|$)"; then
  fail "IB Gateway Paper is not listening on localhost TCP/4002."
fi

cd "$REPO_DIR"

"$VENV_DIR/bin/python" - <<'PY'
from ibapi.client import EClient
from ibapi.wrapper import EWrapper
print("PASS: IBKR Python API available.")
PY

"$VENV_DIR/bin/python" scripts/ibkr_paper_probe.py

echo "PASS: G2 Paper Read-Only proof completed."
echo "Paper order submission: DISABLED"
echo "LIVE trading: DISABLED"
