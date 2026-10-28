#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="project-ce9773ef-6814-469c-92b"
REGION="europe-west3"
ZONE="europe-west3-a"
VM_NAME="aurora-trading-vps"
MACHINE_TYPE="e2-medium"
VPC="aurora-vpc"
SUBNET="aurora-eu3-subnet"
SUBNET_CIDR="10.20.0.0/24"
NETWORK_TAG="aurora-admin"
IMAGE_PROJECT="ubuntu-os-cloud"
IMAGE_FAMILY="ubuntu-minimal-2204-lts"
BOOT_DISK_SIZE="30GB"
BOOT_DISK_TYPE="pd-standard"
IAP_RANGE="35.235.240.0/20"
IAP_SSH_RULE="aurora-allow-iap-ssh"
DENY_PRIVATE_PORTS_RULE="aurora-deny-public-private-ports"

APPLY=0
if [[ "${1:-}" == "--apply" ]]; then
  APPLY=1
elif [[ "${1:-}" == "--plan" || -z "${1:-}" ]]; then
  APPLY=0
else
  echo "Usage: $0 [--plan|--apply]" >&2
  exit 2
fi

log() { printf '\n==> %s\n' "$*"; }
pass() { printf 'PASS: %s\n' "$*"; }
fail() { printf 'FAIL: %s\n' "$*" >&2; exit 1; }

run() {
  printf '+'
  printf ' %q' "$@"
  printf '\n'
  if [[ "$APPLY" -eq 1 ]]; then
    "$@"
  fi
}

command -v gcloud >/dev/null 2>&1 || fail "gcloud CLI is required."

ACTIVE_ACCOUNT="$(gcloud auth list --filter=status:ACTIVE --format='value(account)' | head -n1)"
[[ -n "$ACTIVE_ACCOUNT" ]] || fail "No active gcloud account."

log "AURORA G0/G1 provisioning"
echo "Account: $ACTIVE_ACCOUNT"
echo "Project: $PROJECT_ID"
echo "Region/zone: $REGION / $ZONE"
echo "VM: $VM_NAME ($MACHINE_TYPE)"
echo "OS: Ubuntu 22.04 LTS Minimal"
echo "Disk: $BOOT_DISK_SIZE $BOOT_DISK_TYPE"
echo "Network: $VPC / $SUBNET / $SUBNET_CIDR"
echo "IBKR/VNC public exposure: forbidden (4002/5902)"
echo "Mode: $([[ "$APPLY" -eq 1 ]] && echo APPLY || echo PLAN)"

gcloud projects describe "$PROJECT_ID" >/dev/null   || fail "Active account cannot access target project."

BILLING_ENABLED="$(
  gcloud beta billing projects describe "$PROJECT_ID"     --format='value(billingEnabled)' 2>/dev/null || true
)"
if [[ "${BILLING_ENABLED,,}" == "true" ]]; then
  pass "Billing is enabled."
elif [[ "$APPLY" -eq 1 ]]; then
  fail "Billing is not confirmed enabled for $PROJECT_ID."
else
  echo "INFO: Billing status could not be confirmed in plan mode."
fi

log "Enable required APIs"
run gcloud services enable   compute.googleapis.com   iap.googleapis.com   --project="$PROJECT_ID"

if [[ "$APPLY" -eq 0 ]]; then
  echo "PLAN: resource creation commands are not executed."
fi

log "Ensure custom VPC"
if gcloud compute networks describe "$VPC" --project="$PROJECT_ID" >/dev/null 2>&1; then
  AUTO_SUBNET="$(
    gcloud compute networks describe "$VPC"       --project="$PROJECT_ID"       --format='value(autoCreateSubnetworks)'
  )"
  [[ "${AUTO_SUBNET,,}" == "false" ]]     || fail "Existing $VPC is not custom-subnet mode."
  pass "Existing VPC is custom mode."
else
  run gcloud compute networks create "$VPC"     --project="$PROJECT_ID"     --subnet-mode=custom     --bgp-routing-mode=regional
fi

log "Ensure Frankfurt subnet"
if gcloud compute networks subnets describe "$SUBNET"   --project="$PROJECT_ID"   --region="$REGION" >/dev/null 2>&1; then
  EXISTING_RANGE="$(
    gcloud compute networks subnets describe "$SUBNET"       --project="$PROJECT_ID"       --region="$REGION"       --format='value(ipCidrRange)'
  )"
  EXISTING_NETWORK="$(
    gcloud compute networks subnets describe "$SUBNET"       --project="$PROJECT_ID"       --region="$REGION"       --format='value(network)'
  )"
  [[ "$EXISTING_RANGE" == "$SUBNET_CIDR" ]]     || fail "Existing subnet has unexpected CIDR: $EXISTING_RANGE"
  [[ "$EXISTING_NETWORK" == */networks/"$VPC" ]]     || fail "Existing subnet belongs to another VPC."
  pass "Existing subnet matches security contract."
else
  run gcloud compute networks subnets create "$SUBNET"     --project="$PROJECT_ID"     --network="$VPC"     --range="$SUBNET_CIDR"     --region="$REGION"     --enable-private-ip-google-access
fi

log "Configure firewall: IAP SSH only"
if [[ "$APPLY" -eq 1 ]]; then
  if gcloud compute firewall-rules describe "$IAP_SSH_RULE"     --project="$PROJECT_ID" >/dev/null 2>&1; then
    gcloud compute firewall-rules delete "$IAP_SSH_RULE"       --project="$PROJECT_ID" --quiet
  fi
  gcloud compute firewall-rules create "$IAP_SSH_RULE"     --project="$PROJECT_ID"     --network="$VPC"     --direction=INGRESS     --priority=1000     --action=ALLOW     --rules=tcp:22     --source-ranges="$IAP_RANGE"     --target-tags="$NETWORK_TAG"     --description="AURORA SSH via Google IAP only"
else
  echo "+ gcloud compute firewall-rules create $IAP_SSH_RULE ... source=$IAP_RANGE tcp:22"
fi

log "Configure firewall: explicit public deny for IBKR API and VNC"
if [[ "$APPLY" -eq 1 ]]; then
  if gcloud compute firewall-rules describe "$DENY_PRIVATE_PORTS_RULE"     --project="$PROJECT_ID" >/dev/null 2>&1; then
    gcloud compute firewall-rules delete "$DENY_PRIVATE_PORTS_RULE"       --project="$PROJECT_ID" --quiet
  fi
  gcloud compute firewall-rules create "$DENY_PRIVATE_PORTS_RULE"     --project="$PROJECT_ID"     --network="$VPC"     --direction=INGRESS     --priority=900     --action=DENY     --rules=tcp:4002,tcp:5902     --source-ranges=0.0.0.0/0     --target-tags="$NETWORK_TAG"     --description="Never expose AURORA IBKR API or VNC publicly"
else
  echo "+ gcloud compute firewall-rules create $DENY_PRIVATE_PORTS_RULE ... deny tcp:4002,tcp:5902"
fi

log "Grant current operator minimum IAP/OS Login roles"
if [[ "$ACTIVE_ACCOUNT" == *.gserviceaccount.com ]]; then
  MEMBER="serviceAccount:$ACTIVE_ACCOUNT"
else
  MEMBER="user:$ACTIVE_ACCOUNT"
fi
run gcloud projects add-iam-policy-binding "$PROJECT_ID"   --member="$MEMBER"   --role="roles/iap.tunnelResourceAccessor"   --quiet
run gcloud projects add-iam-policy-binding "$PROJECT_ID"   --member="$MEMBER"   --role="roles/compute.osAdminLogin"   --quiet

log "Create hardened VM"
if gcloud compute instances describe "$VM_NAME"   --project="$PROJECT_ID"   --zone="$ZONE" >/dev/null 2>&1; then
  pass "VM already exists; creation skipped."
else
  STARTUP_FILE="$(mktemp)"
  trap 'rm -f "${STARTUP_FILE:-}"' EXIT

  cat >"$STARTUP_FILE" <<'STARTUP'
#!/usr/bin/env bash
set -euo pipefail

install -d -m 0755 /etc/ssh/sshd_config.d
cat >/etc/ssh/sshd_config.d/99-aurora-hardening.conf <<'EOF'
PasswordAuthentication no
KbdInteractiveAuthentication no
PermitRootLogin no
EOF

if command -v sshd >/dev/null 2>&1; then
  sshd -t
fi

systemctl reload ssh 2>/dev/null || systemctl reload sshd 2>/dev/null || true
install -d -m 0755 /opt/aurora
STARTUP

  run gcloud compute instances create "$VM_NAME"     --project="$PROJECT_ID"     --zone="$ZONE"     --machine-type="$MACHINE_TYPE"     --network-interface="network=$VPC,subnet=$SUBNET,network-tier=PREMIUM"     --tags="$NETWORK_TAG"     --labels="app=aurora,broker-mode=paper"     --image-project="$IMAGE_PROJECT"     --image-family="$IMAGE_FAMILY"     --boot-disk-size="$BOOT_DISK_SIZE"     --boot-disk-type="$BOOT_DISK_TYPE"     --metadata="enable-oslogin=TRUE"     --metadata-from-file="startup-script=$STARTUP_FILE"     --shielded-secure-boot     --shielded-vtpm     --shielded-integrity-monitoring     --deletion-protection     --no-service-account     --no-scopes
fi

if [[ "$APPLY" -eq 0 ]]; then
  log "PLAN COMPLETE"
  echo "Re-run with --apply to create the approved resources."
  exit 0
fi

log "Verify VM contract"
VM_JSON_FILE="$(mktemp)"
trap 'rm -f "${STARTUP_FILE:-}" "${VM_JSON_FILE:-}"' EXIT

gcloud compute instances describe "$VM_NAME" \
  --project="$PROJECT_ID" \
  --zone="$ZONE" \
  --format=json >"$VM_JSON_FILE"

python3 - "$VM_NAME" "$MACHINE_TYPE" "$VPC" "$SUBNET" "$VM_JSON_FILE" <<'PY'
import json
import sys

vm_name, machine, vpc, subnet, json_path = sys.argv[1:]
with open(json_path, "r", encoding="utf-8") as handle:
    data = json.load(handle)

assert data["name"] == vm_name
assert data["machineType"].endswith("/machineTypes/" + machine)
assert len(data.get("networkInterfaces", [])) == 1
nic = data["networkInterfaces"][0]
assert nic["network"].endswith("/networks/" + vpc)
assert nic["subnetwork"].endswith("/subnetworks/" + subnet)
assert data.get("deletionProtection") is True
assert data.get("shieldedInstanceConfig", {}).get("enableSecureBoot") is True
assert data.get("shieldedInstanceConfig", {}).get("enableVtpm") is True
assert data.get("shieldedInstanceConfig", {}).get("enableIntegrityMonitoring") is True
metadata = {
    item["key"]: item["value"]
    for item in data.get("metadata", {}).get("items", [])
}
assert metadata.get("enable-oslogin") == "TRUE"
assert data.get("serviceAccounts", []) == []
print("PASS: VM configuration matches AURORA contract.")
PY

EXTERNAL_IP="$(
  gcloud compute instances describe "$VM_NAME"     --project="$PROJECT_ID"     --zone="$ZONE"     --format='value(networkInterfaces[0].accessConfigs[0].natIP)'
)"

[[ -n "$EXTERNAL_IP" ]] || fail "Expected ephemeral external IPv4 was not assigned."
pass "Ephemeral external IPv4 assigned: $EXTERNAL_IP"

log "Verify IAP SSH and local SSH hardening"
SSH_OK=0
for _ in 1 2 3 4 5 6 7 8; do
  if gcloud compute ssh "$VM_NAME"     --project="$PROJECT_ID"     --zone="$ZONE"     --tunnel-through-iap     --quiet     --command='
      set -e
      echo "IAP_SSH_OK"
      sudo sshd -T | grep -qx "passwordauthentication no"
      sudo sshd -T | grep -qx "permitrootlogin no"
      if sudo ss -lntH | awk '"'"'$4 ~ /(^|:)4002$/ && ($4 ~ /^0\.0\.0\.0:/ || $4 ~ /^\[::\]:/ || $4 ~ /^\*:/) {found=1} END{exit !found}'"'"'; then
        echo "PUBLIC_4002_BIND_DETECTED" >&2
        exit 21
      fi
      if sudo ss -lntH | awk '"'"'$4 ~ /(^|:)5902$/ && ($4 ~ /^0\.0\.0\.0:/ || $4 ~ /^\[::\]:/ || $4 ~ /^\*:/) {found=1} END{exit !found}'"'"'; then
        echo "PUBLIC_5902_BIND_DETECTED" >&2
        exit 22
      fi
    ' >/tmp/aurora-iap-verify.out 2>/tmp/aurora-iap-verify.err; then
    SSH_OK=1
    cat /tmp/aurora-iap-verify.out
    break
  fi
  sleep 5
done
[[ "$SSH_OK" -eq 1 ]] || {
  cat /tmp/aurora-iap-verify.err >&2 || true
  fail "IAP SSH verification failed."
}

log "Negative test: public ports must be unreachable"
if command -v nc >/dev/null 2>&1; then
  for PORT in 22 4002 5902; do
    if nc -z -w 3 "$EXTERNAL_IP" "$PORT" >/dev/null 2>&1; then
      fail "Public TCP/$PORT is reachable at $EXTERNAL_IP."
    else
      pass "Public TCP/$PORT is blocked."
    fi
  done
else
  echo "INFO: nc is unavailable; external negative tests must be run separately."
fi

log "Provisioning complete"
echo "G0/G1 status: PASS if all checks above passed."
echo "LIVE trading: DISABLED"
echo "Paper order submission: DISABLED"
echo "Next gate: G2 IBKR Paper Read-Only."
