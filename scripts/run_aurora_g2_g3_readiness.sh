#!/usr/bin/env bash
set -euo pipefail

AURORA_HOME="${AURORA_HOME:-$HOME/aurora}"
REPO_DIR="$AURORA_HOME/news-stock-scanner"
VENV_DIR="$AURORA_HOME/venv"
ENV_FILE="$HOME/.config/aurora/ibkr-paper.env"
FIXED_G3_OUTPUT="$REPO_DIR/runtime/ibkr_market_data/latest.json"
SYMBOL="${1:-BKR}"

fail() {
  printf 'FAIL: %s\n' "$*" >&2
  exit 1
}

[[ "$(id -u)" -ne 0 ]] || fail "Run as the normal OS Login user, not root."
[[ "$SYMBOL" =~ ^[A-Z][A-Z0-9.-]{0,9}$ ]] || fail "Invalid stock symbol."
[[ -x "$VENV_DIR/bin/python" ]] || fail "Python venv missing."
[[ -d "$REPO_DIR/.git" ]] || fail "AURORA repository missing."
[[ -f "$ENV_FILE" && ! -L "$ENV_FILE" ]] || fail "Runtime env must be a regular non-symlink file."
[[ "$(stat -c %u "$ENV_FILE")" == "$(id -u)" ]] || fail "Runtime env owner is invalid."
[[ "$(stat -c %a "$ENV_FILE")" == "600" ]] || fail "Runtime env mode must be 600."
[[ "$(stat -c %h "$ENV_FILE")" == "1" ]] || fail "Runtime env hard links are forbidden."

declare -A seen_keys=()

while IFS= read -r line || [[ -n "$line" ]]; do
  [[ -z "$line" ]] && continue
  [[ "${line:0:1}" == "#" ]] && continue
  [[ "$line" != *$'\r'* ]] || fail "Runtime env contains CR characters."
  [[ "$line" == *=* ]] || fail "Runtime env contains a malformed line."

  key="${line%%=*}"
  value="${line#*=}"

  case "$key" in
    AURORA_RUN_MODE|AURORA_IBKR_ENABLED|AURORA_IBKR_MODE|AURORA_IBKR_HOST|AURORA_IBKR_PORT|AURORA_IBKR_CLIENT_ID|AURORA_IBKR_TIMEOUT_SECONDS|AURORA_IBKR_PAPER_ACCOUNT_ALLOWLIST|AURORA_IBKR_MARKET_DATA_ENABLED|AURORA_IBKR_MARKET_DATA_CLIENT_ID|AURORA_IBKR_MARKET_DATA_TIMEOUT_SECONDS)
      ;;
    *)
      fail "Runtime env contains an unapproved key."
      ;;
  esac

  [[ -z "${seen_keys[$key]+x}" ]] || fail "Runtime env contains a duplicate key."
  seen_keys["$key"]=1

  [[ "$value" != *[[:space:]]* ]] || fail "Runtime env values may not contain whitespace."
  export "$key=$value"
done <"$ENV_FILE"

required_keys=(
  AURORA_RUN_MODE
  AURORA_IBKR_ENABLED
  AURORA_IBKR_MODE
  AURORA_IBKR_HOST
  AURORA_IBKR_PORT
  AURORA_IBKR_CLIENT_ID
  AURORA_IBKR_TIMEOUT_SECONDS
  AURORA_IBKR_PAPER_ACCOUNT_ALLOWLIST
  AURORA_IBKR_MARKET_DATA_ENABLED
  AURORA_IBKR_MARKET_DATA_CLIENT_ID
  AURORA_IBKR_MARKET_DATA_TIMEOUT_SECONDS
)

for key in "${required_keys[@]}"; do
  [[ -n "${seen_keys[$key]+x}" ]] || fail "Runtime env is missing a required key."
done

[[ "${AURORA_RUN_MODE:-}" == "READ_ONLY" ]] || fail "AURORA_RUN_MODE must be READ_ONLY."
[[ "${AURORA_IBKR_ENABLED:-}" == "true" ]] || fail "AURORA_IBKR_ENABLED must be true."
[[ "${AURORA_IBKR_MODE:-}" == "PAPER" ]] || fail "IBKR mode must be PAPER."
[[ "${AURORA_IBKR_HOST:-}" == "127.0.0.1" ]] || fail "IBKR host must be loopback."
[[ "${AURORA_IBKR_PORT:-}" == "4002" ]] || fail "IBKR Paper port must be 4002."
[[ "${AURORA_IBKR_CLIENT_ID:-}" =~ ^[1-9][0-9]*$ ]] || fail "G2 client ID must be positive."
[[ "${AURORA_IBKR_MARKET_DATA_CLIENT_ID:-}" =~ ^[1-9][0-9]*$ ]] || fail "G3 client ID must be positive."
[[ "${AURORA_IBKR_MARKET_DATA_CLIENT_ID}" -le 2147483647 ]] || fail "G3 client ID is out of range."
[[ "${AURORA_IBKR_MARKET_DATA_CLIENT_ID}" != "${AURORA_IBKR_CLIENT_ID}" ]] || fail "G2 and G3 must use distinct API client IDs."
[[ "${AURORA_IBKR_MARKET_DATA_TIMEOUT_SECONDS:-}" =~ ^[0-9]+([.][0-9]+)?$ ]] || fail "G3 timeout format is invalid."
[[ "${AURORA_IBKR_PAPER_ACCOUNT_ALLOWLIST:-}" =~ ^DU[[:alnum:]]+$ ]] || fail "Exactly one valid Paper account allowlist entry is required."
[[ "${AURORA_IBKR_PAPER_ACCOUNT_ALLOWLIST}" != "DUXXXXXXX" ]] || fail "Placeholder account ID is not allowed."

cd "$REPO_DIR"

readonly AURORA_EVIDENCE_RUN_ID="$(
  "$VENV_DIR/bin/python" -c 'import uuid; print(uuid.uuid4())'
)"
export AURORA_EVIDENCE_RUN_ID

echo "==> G2 strict Paper Read-Only proof"
g2_status=0
bash scripts/run_aurora_g2_readonly.sh || g2_status=$?

if (( g2_status != 0 )); then
  printf 'FAIL: G2 status=%d. G3 was not attempted.\n' "$g2_status" >&2
  echo "Paper order submission: DISABLED"
  echo "LIVE trading: DISABLED"
  exit 2
fi

echo "==> G3 verified real-time market-data proof for $SYMBOL"
export AURORA_IBKR_MARKET_DATA_ENABLED=true
export AURORA_IBKR_MARKET_DATA_PROBE_OUTPUT="$FIXED_G3_OUTPUT"

g3_status=0
"$VENV_DIR/bin/python" scripts/ibkr_market_data_probe.py "$SYMBOL" || g3_status=$?

echo "==> Unified fail-closed readiness decision"
summary_status=0
"$VENV_DIR/bin/python" scripts/aurora_readiness_summary.py || summary_status=$?

if (( g3_status != 0 || summary_status != 0 )); then
  printf 'FAIL: G3 status=%d, summary status=%d.\n' \
    "$g3_status" "$summary_status" >&2
  echo "Paper order submission: DISABLED"
  echo "LIVE trading: DISABLED"
  exit 2
fi

printf '%s\n' \
  "PASS: Fresh G2/G3 evidence is ready for controlled G4 dry-run." \
  "Paper order submission: DISABLED" \
  "LIVE trading: DISABLED"
