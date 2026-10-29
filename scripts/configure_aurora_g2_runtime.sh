#!/usr/bin/env bash
set -euo pipefail

CONFIG_DIR="$HOME/.config/aurora"
ENV_FILE="$CONFIG_DIR/ibkr-paper.env"

fail() { printf 'FAIL: %s\n' "$*" >&2; exit 1; }

install -d -m 0700 "$CONFIG_DIR"
[[ -f "$ENV_FILE" ]] || fail "Run bootstrap_aurora_g2_vps.sh first."

printf "Enter the IBKR PAPER account ID (input hidden): "
IFS= read -rs PAPER_ACCOUNT
printf "\n"

PAPER_ACCOUNT="$(printf '%s' "$PAPER_ACCOUNT" | tr -d '[:space:]')"
[[ -n "$PAPER_ACCOUNT" ]] || fail "Paper account ID cannot be empty."
[[ "$PAPER_ACCOUNT" != "DUXXXXXXX" ]] || fail "Placeholder account ID is not allowed."

TMP="$(mktemp)"
trap 'rm -f "$TMP"' EXIT

awk -v acct="$PAPER_ACCOUNT" '
BEGIN {seen_allow=0; seen_enabled=0}
$0 ~ /^AURORA_IBKR_PAPER_ACCOUNT_ALLOWLIST=/ {
  print "AURORA_IBKR_PAPER_ACCOUNT_ALLOWLIST=" acct
  seen_allow=1
  next
}
$0 ~ /^AURORA_IBKR_ENABLED=/ {
  print "AURORA_IBKR_ENABLED=true"
  seen_enabled=1
  next
}
{print}
END {
  if (!seen_allow) print "AURORA_IBKR_PAPER_ACCOUNT_ALLOWLIST=" acct
  if (!seen_enabled) print "AURORA_IBKR_ENABLED=true"
}
' "$ENV_FILE" >"$TMP"

install -m 0600 "$TMP" "$ENV_FILE"

unset PAPER_ACCOUNT

echo "PASS: G2 runtime configured without printing the Paper account ID."
echo "LIVE trading: DISABLED"
echo "Paper order submission: DISABLED"
