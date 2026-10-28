# AURORA V8.9.5 — G0/G1 Deployment & Acceptance Contract

This document is the deployment contract for the first AURORA VPS milestone.
It does not authorize creation of a paid Google Cloud resource. VM creation
requires explicit user approval after the final cost review.

## G0 — Infrastructure target

- Project: `project-ce9773ef-6814-469c-92b`
- Instance: `aurora-trading-vps`
- Region / zone: `europe-west3 / europe-west3-a`
- Machine: `e2-medium`
- OS: Ubuntu 22.04 LTS Minimal
- Boot disk: 30 GB `pd-standard`
- Network: `aurora-vpc`
- Subnet: `aurora-eu3-subnet`, `10.20.0.0/24`
- Exactly one NIC

The canonical machine-readable values are in
`deployment_engine/vps_security_contract.json`.

## G1 — Secure access target

Inbound exposure must be minimal:

- TCP/22: allowed only from Google Cloud IAP source `35.235.240.0/20`.
- TCP/4002: no public ingress rule.
- TCP/5902: no public ingress rule.
- HTTP/HTTPS: disabled unless a later approved milestone requires them.
- OS Login: enabled.
- SSH password authentication: disabled.
- Root password login: disabled.

An ephemeral external IPv4 may be used for outbound connectivity during the
single-VM pilot. Its presence must not imply public access to 22/4002/5902.

## IBKR local binding

First broker milestone:

- Mode: PAPER only.
- IB Gateway host: `127.0.0.1`
- IB Gateway port: `4002`
- VNC, if required for Gateway GUI authentication: bind to `127.0.0.1:5902`
  and reach it only through a secure tunnel.
- Paper account must match the runtime-only allowlist.
- Order submission remains disabled during G2 read-only proof.

## Runtime bootstrap

Use `config/aurora_runtime.env.example` as the safe template.

Initial state must be:

```text
AURORA_RUN_MODE=SAFE_OFF
AURORA_IBKR_ENABLED=false
```

Do not enable the IBKR connector until IB Gateway is installed, logged into
the Paper account, API Read-Only is enabled, and the real Paper account ID
has been configured only in the VPS runtime environment.

## Acceptance sequence

### Cloud-side evidence

Before G0/G1 can pass, capture evidence that:

1. VPC/subnet names and CIDR match the contract.
2. VM has one NIC and the approved machine/OS/disk configuration.
3. No `0.0.0.0/0 -> tcp:22` ingress exists for AURORA.
4. The only approved SSH ingress is IAP `35.235.240.0/20 -> tcp:22`.
5. No ingress firewall rule exposes TCP/4002 or TCP/5902.
6. OS Login is enabled.

### VM-side evidence

From the repository root run:

```bash
bash scripts/verify_g0_g1_local.sh
```

Expected result:

```text
G0/G1 LOCAL RESULT: PASS
```

### External negative tests

From a non-IAP external host, direct connection attempts to the VM public IP
must fail for:

- TCP/22
- TCP/4002
- TCP/5902

IAP SSH must still work.

## Gate rule

Only when cloud-side evidence, local verification, and external negative tests
all pass may AURORA move from G0/G1 to G2 Paper Read-Only.

No test in this document authorizes real-money trading.
