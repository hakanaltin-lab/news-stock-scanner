# AURORA V8.9.8 — Google Cloud G0/G1 Provisioning

This package provisions the approved AURORA VPS architecture in Google Cloud.

## User approval

The user explicitly approved creation of the paid VM on 2026-10-28.
This approval covers the Google Cloud infrastructure only. It does not enable
IBKR Paper order submission or real-money trading.

## Target

- Project: `project-ce9773ef-6814-469c-92b`
- VM: `aurora-trading-vps`
- Region: `europe-west3`
- Zone: `europe-west3-a`
- Machine: `e2-medium`
- OS: Ubuntu 22.04 LTS Minimal
- Disk: 30 GB Standard Persistent Disk
- VPC: `aurora-vpc`
- Subnet: `aurora-eu3-subnet`, `10.20.0.0/24`
- External IPv4: ephemeral
- Service account: none
- OAuth scopes: none
- OS Login: enabled
- Shielded VM: Secure Boot + vTPM + integrity monitoring
- Deletion protection: enabled

## Firewall

The provisioning script creates:

1. IAP-only SSH allow rule:
   - source: `35.235.240.0/20`
   - target tag: `aurora-admin`
   - TCP/22 only
2. Explicit deny rule for public broker/private GUI ports:
   - source: `0.0.0.0/0`
   - TCP/4002
   - TCP/5902

No HTTP or HTTPS ingress rule is created.

## Safe execution model

The script defaults to PLAN mode:

```bash
bash scripts/provision_aurora_gcp.sh --plan
```

Only `--apply` creates or changes resources:

```bash
bash scripts/provision_aurora_gcp.sh --apply
```

The script is designed to be re-runnable. Existing VPC/subnet objects are
validated against the contract before reuse. A pre-existing VM is not
recreated.

## Post-create verification

The script verifies:

- one NIC
- expected network and subnet
- deletion protection
- Shielded VM settings
- OS Login metadata
- no VM service account
- IAP SSH succeeds
- SSH password authentication is disabled
- root SSH login is disabled
- TCP/4002 and TCP/5902 are not publicly bound
- external direct TCP/22, TCP/4002 and TCP/5902 fail

A successful run ends with:

```text
G0/G1 status: PASS
LIVE trading: DISABLED
Paper order submission: DISABLED
Next gate: G2 IBKR Paper Read-Only.
```

## Cloud Shell one-command path

After this script is merged to `main`, the approved provisioning can be
started from Google Cloud Shell with:

```bash
curl -fsSL https://raw.githubusercontent.com/hakanaltin-lab/news-stock-scanner/main/scripts/provision_aurora_gcp.sh -o /tmp/provision_aurora_gcp.sh && bash /tmp/provision_aurora_gcp.sh --apply
```

The active Google Cloud account must have permission to create Compute Engine,
VPC, firewall and project IAM resources in the target project.

## Cost

The Google Cloud console estimate observed before approval was approximately
USD 32.95/month for e2-medium plus a 30 GB standard persistent disk, before
additional items such as external IPv4, network usage, logs, or other optional
services. The existing TRY 750 budget alert is a notification threshold, not
a spending cap.

No real-money trading action is authorized by this deployment.
