#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="project-ce9773ef-6814-469c-92b"
ZONE="europe-west3-a"
VM_NAME="aurora-trading-vps"
RAW_BASE="https://raw.githubusercontent.com/hakanaltin-lab/news-stock-scanner/main"

fail() { printf 'FAIL: %s\n' "$*" >&2; exit 1; }
log() { printf '\n==> %s\n' "$*"; }

command -v gcloud >/dev/null 2>&1 || fail "Run this from Google Cloud Shell or a machine with gcloud installed."

ACTIVE_ACCOUNT="$(gcloud auth list --filter=status:ACTIVE --format='value(account)' | head -n1)"
[[ -n "$ACTIVE_ACCOUNT" ]] || fail "No active gcloud account."

log "Step 1/4 — Provision approved G0/G1 infrastructure"
PROVISION_SCRIPT="$(mktemp)"
GCP_PROOF_PATH="$(mktemp)"
trap 'rm -f "$PROVISION_SCRIPT" "$GCP_PROOF_PATH"' EXIT

curl -fsSL "$RAW_BASE/scripts/provision_aurora_gcp.sh" -o "$PROVISION_SCRIPT"
export AURORA_GCP_PROOF_OUTPUT="$GCP_PROOF_PATH"
bash "$PROVISION_SCRIPT" --apply

log "Step 2/4 — Confirm VM is RUNNING"
STATUS="$(
  gcloud compute instances describe "$VM_NAME" \
    --project="$PROJECT_ID" \
    --zone="$ZONE" \
    --format='value(status)'
)"
[[ "$STATUS" == "RUNNING" ]] || fail "VM status is $STATUS, expected RUNNING."

log "Step 3/4 — Bootstrap G2 over IAP SSH"
REMOTE_BOOTSTRAP='
set -euo pipefail
TMP="$(mktemp)"
trap '"'"'rm -f "$TMP"'"'"' EXIT
curl -fsSL https://raw.githubusercontent.com/hakanaltin-lab/news-stock-scanner/main/scripts/bootstrap_aurora_g2_vps.sh -o "$TMP"
bash "$TMP"
bash "$HOME/aurora/news-stock-scanner/scripts/download_ibgateway_stable.sh"
'

gcloud compute ssh "$VM_NAME" \
  --project="$PROJECT_ID" \
  --zone="$ZONE" \
  --tunnel-through-iap \
  --quiet \
  --command="$REMOTE_BOOTSTRAP"

log "Step 4/4 — Verify remote G2 baseline"
REMOTE_VERIFY='
set -euo pipefail
test -x "$HOME/aurora/venv/bin/python"
test -d "$HOME/aurora/news-stock-scanner/.git"
test -f "$HOME/.config/aurora/ibkr-paper.env"
test "$(stat -c %a "$HOME/.config/aurora/ibkr-paper.env")" = "600"
grep -qx "AURORA_RUN_MODE=READ_ONLY" "$HOME/.config/aurora/ibkr-paper.env"
grep -qx "AURORA_IBKR_ENABLED=false" "$HOME/.config/aurora/ibkr-paper.env"
grep -qx "AURORA_IBKR_MODE=PAPER" "$HOME/.config/aurora/ibkr-paper.env"
grep -qx "AURORA_IBKR_HOST=127.0.0.1" "$HOME/.config/aurora/ibkr-paper.env"
grep -qx "AURORA_IBKR_PORT=4002" "$HOME/.config/aurora/ibkr-paper.env"
grep -qx "AURORA_IBKR_MARKET_DATA_ENABLED=false" "$HOME/.config/aurora/ibkr-paper.env"

for port in 4002 5902; do
  if sudo ss -lntH | awk -v p=":$port" '"'"'
    $4 ~ p"$" && (
      $4 ~ /^0\.0\.0\.0:/ ||
      $4 ~ /^\[::\]:/ ||
      $4 ~ /^\*:/
    ) {found=1}
    END {exit !found}
  '"'"'; then
    echo "FAIL: TCP/$port is publicly bound." >&2
    exit 20
  fi
done

echo "PASS: G2 baseline installed; broker remains disabled."
'

gcloud compute ssh "$VM_NAME" \
  --project="$PROJECT_ID" \
  --zone="$ZONE" \
  --tunnel-through-iap \
  --quiet \
  --command="$REMOTE_VERIFY"

log "Persist sanitized G0/G1 proof on the VPS"
gcloud compute ssh "$VM_NAME" \
  --project="$PROJECT_ID" \
  --zone="$ZONE" \
  --tunnel-through-iap \
  --quiet \
  --command='mkdir -p "$HOME/aurora/news-stock-scanner/runtime/gcp"'
gcloud compute scp "$GCP_PROOF_PATH" \
  "$VM_NAME:~/aurora/news-stock-scanner/runtime/gcp/latest.json" \
  --project="$PROJECT_ID" \
  --zone="$ZONE" \
  --tunnel-through-iap \
  --quiet

cat <<'EOF'

============================================================
AURORA G0/G1 + G2 BASELINE COMPLETE
============================================================

Infrastructure:
  VM: aurora-trading-vps
  Zone: europe-west3-a

Safety:
  LIVE trading: DISABLED
  Paper order submission: DISABLED
  Broker connector: DISABLED
  Market-data connector: DISABLED
  Public TCP/4002: BLOCKED
  Public TCP/5902: BLOCKED

Prepared:
  XFCE + TigerVNC
  AURORA repository
  Python virtual environment
  Protected Paper runtime env
  Official IB Gateway Stable installer downloaded

Manual security-required steps still remain:
  1. Create a VNC password.
  2. Start localhost-only VNC.
  3. Install and launch IB Gateway in the VNC desktop.
  4. Log in manually to IBKR PAPER and complete 2FA.
  5. Install the official TWS API ZIP.
  6. Configure the Paper account runtime allowlist.
  7. Run G2 Paper Read-Only proof.

No real-money permission has been enabled.
============================================================
EOF
