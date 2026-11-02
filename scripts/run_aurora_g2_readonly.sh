#!/usr/bin/env bash
set -euo pipefail

AURORA_HOME="${AURORA_HOME:-$HOME/aurora}"
REPO_DIR="$AURORA_HOME/news-stock-scanner"
VENV_DIR="$AURORA_HOME/venv"
ENV_FILE="$HOME/.config/aurora/ibkr-paper.env"
FIXED_G2_OUTPUT="$REPO_DIR/runtime/ibkr_paper_read_only/latest.json"
INHERITED_EVIDENCE_RUN_ID="${AURORA_EVIDENCE_RUN_ID:-}"

fail() {
  printf 'FAIL: %s\n' "$*" >&2
  exit 1
}

[[ "$(id -u)" -ne 0 ]] || fail "Run as the normal OS Login user, not root."
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
)

for key in "${required_keys[@]}"; do
  [[ -n "${seen_keys[$key]+x}" ]] || fail "Runtime env is missing a required key."
done

[[ "${AURORA_RUN_MODE:-}" == "READ_ONLY" ]] || fail "AURORA_RUN_MODE must be READ_ONLY."
[[ "${AURORA_IBKR_ENABLED:-}" == "true" ]] || fail "AURORA_IBKR_ENABLED must be true."
[[ "${AURORA_IBKR_MODE:-}" == "PAPER" ]] || fail "AURORA_IBKR_MODE must be PAPER."
[[ "${AURORA_IBKR_HOST:-}" == "127.0.0.1" ]] || fail "IBKR host must be 127.0.0.1."
[[ "${AURORA_IBKR_PORT:-}" == "4002" ]] || fail "IBKR Paper port must be 4002."
[[ "${AURORA_IBKR_CLIENT_ID:-}" =~ ^[1-9][0-9]*$ ]] || fail "IBKR client ID must be a positive integer."
[[ "${AURORA_IBKR_CLIENT_ID}" -le 2147483647 ]] || fail "IBKR client ID is out of range."
[[ "${AURORA_IBKR_PAPER_ACCOUNT_ALLOWLIST:-}" =~ ^DU[[:alnum:]]+$ ]] || fail "Exactly one valid Paper account allowlist entry is required."
[[ "${AURORA_IBKR_PAPER_ACCOUNT_ALLOWLIST}" != "DUXXXXXXX" ]] || fail "Placeholder account ID is not allowed."

if [[ -n "$INHERITED_EVIDENCE_RUN_ID" ]]; then
  [[ "$INHERITED_EVIDENCE_RUN_ID" =~ ^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$ ]] ||     fail "Inherited evidence run ID must be canonical UUIDv4."
  EVIDENCE_RUN_ID="$INHERITED_EVIDENCE_RUN_ID"
else
  EVIDENCE_RUN_ID="$("$VENV_DIR/bin/python" - <<'PY'
from uuid import uuid4
print(uuid4())
PY
)"
fi

export AURORA_EVIDENCE_RUN_ID="$EVIDENCE_RUN_ID"
export AURORA_IBKR_PROBE_OUTPUT="$FIXED_G2_OUTPUT"

cd "$REPO_DIR"

"$VENV_DIR/bin/python" scripts/verify_gateway_readonly_attestation.py

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

"$VENV_DIR/bin/python" - <<'PY'
from ibapi.client import EClient
from ibapi.wrapper import EWrapper
print("PASS: official IBKR Python API available.")
PY

set +e
"$VENV_DIR/bin/python" scripts/ibkr_paper_probe.py
probe_rc=$?
set -e

[[ "$probe_rc" -eq 0 ]] || fail "Strict G2 probe did not reach READY_FOR_PAPER_READ_ONLY."

"$VENV_DIR/bin/python" scripts/g2_post_review_status.py \
  --expected-run-id "$EVIDENCE_RUN_ID"

printf '%s\n' \
  "PASS: G2 Paper Read-Only proof completed and bound to this fresh evidence run." \
  "Paper order submission: DISABLED" \
  "LIVE trading: DISABLED" \
  "Next: G3 verified real-time market-data probe."
