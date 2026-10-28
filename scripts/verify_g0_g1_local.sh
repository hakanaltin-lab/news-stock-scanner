#!/usr/bin/env bash
set -euo pipefail

failures=0

pass() { printf 'PASS: %s\n' "$1"; }
fail() { printf 'FAIL: %s\n' "$1"; failures=$((failures + 1)); }

echo "AURORA V8.9.5 G0/G1 local security verification"

if command -v python3 >/dev/null 2>&1; then
  mode="$(python3 - <<'PY'
from engines.aurora_run_mode_engine import load_run_mode
print(load_run_mode()["mode"])
PY
)"
  case "$mode" in
    SAFE_OFF|READ_ONLY) pass "run mode is fail-closed ($mode)" ;;
    *) fail "run mode must be SAFE_OFF or READ_ONLY during G0/G1, got $mode" ;;
  esac
else
  fail "python3 is not installed"
fi

if command -v sshd >/dev/null 2>&1; then
  sshd_effective="$(sshd -T 2>/dev/null || true)"
  if grep -qi '^passwordauthentication no$' <<<"$sshd_effective"; then
    pass "SSH password authentication disabled"
  else
    fail "SSH PasswordAuthentication must be no"
  fi

  if grep -Eqi '^permitrootlogin (no|prohibit-password)$' <<<"$sshd_effective"; then
    pass "SSH root password login disabled"
  else
    fail "SSH PermitRootLogin must be no/prohibit-password"
  fi
else
  fail "sshd is not installed"
fi

if command -v ss >/dev/null 2>&1; then
  listeners="$(ss -lntH || true)"

  if awk '$4 ~ /(^|:)4002$/ && ($4 ~ /^0\.0\.0\.0:/ || $4 ~ /^\[::\]:/ || $4 ~ /^\*:/) {found=1} END{exit !found}' <<<"$listeners"; then
    fail "IBKR API 4002 is listening publicly"
  else
    pass "IBKR API 4002 is not publicly bound"
  fi

  if awk '$4 ~ /(^|:)5902$/ && ($4 ~ /^0\.0\.0\.0:/ || $4 ~ /^\[::\]:/ || $4 ~ /^\*:/) {found=1} END{exit !found}' <<<"$listeners"; then
    fail "VNC 5902 is listening publicly"
  else
    pass "VNC 5902 is not publicly bound"
  fi
else
  fail "ss command is unavailable"
fi

if command -v curl >/dev/null 2>&1; then
  oslogin="$(curl -fsS -H 'Metadata-Flavor: Google' 'http://metadata.google.internal/computeMetadata/v1/instance/attributes/enable-oslogin' 2>/dev/null || true)"
  if [[ "${oslogin,,}" == "true" ]]; then
    pass "instance metadata enable-oslogin=true"
  else
    echo "INFO: instance-level enable-oslogin is not true; verify project-level OS Login metadata in GCP"
  fi
fi

if [[ "$failures" -ne 0 ]]; then
  printf 'G0/G1 LOCAL RESULT: FAIL (%d failure(s))\n' "$failures"
  exit 2
fi

echo "G0/G1 LOCAL RESULT: PASS"
echo "NOTE: Cloud firewall/IAP reachability must also be verified from outside the VM."
