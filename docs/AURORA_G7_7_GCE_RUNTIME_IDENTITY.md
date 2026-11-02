# AURORA G7.7 — Live GCE Runtime Identity Binding

G7.7 prevents a valid Gateway/TWS Read-Only attestation from being replayed on a
different or recreated VPS that merely shares the same hostname.

It does not enable Paper orders, LIVE execution, automatic promotion or
real-money trading.

## Runtime identity source

AURORA reads only four non-secret values from the Google Compute Engine
link-local metadata service:

- project ID;
- instance name;
- zone;
- immutable numeric instance ID.

The endpoint is fixed to:

```text
http://169.254.169.254/computeMetadata/v1
```

The reader:

- disables HTTP proxy use;
- rejects redirects;
- requires the `Metadata-Flavor: Google` response header;
- limits each response to 1024 bytes;
- does not accept environment/CLI URL overrides;
- never requests service-account, token, credential or user-data metadata.

## Approved runtime

The runtime identity must resolve to:

```text
project = project-ce9773ef-6814-469c-92b
instance = aurora-trading-vps
zone = europe-west3-a
```

The numeric GCE instance ID is intentionally not hard-coded in Git. The actual
ID must be copied from the independently checked live VPS into the root-owned
attestation policy and then into the reviewer-signed V2 artifact.

## V2 signed attestation

G7.7 upgrades the signed attestation contract to:

```text
schema_version = 2
attestation_type = IBKR_GATEWAY_API_READ_ONLY_V2
```

The signature now covers both:

- `gcp_project_id`;
- `gcp_instance_id`.

The root-owned policy also pins:

- `expected_project_id`;
- `expected_instance_id`.

A positive attestation therefore requires equality across all three sources:

1. reviewer-signed artifact;
2. root-controlled reviewer policy;
3. live GCE link-local metadata.

The G7.6 reviewer handoff additionally cross-checks the same immutable instance ID
against the sanitized G0/G1 control-plane proof generated from
`gcloud compute instances describe`. This creates an independent second runtime
identity source before reviewer handoff: GCP control-plane VM JSON and in-guest
link-local metadata must agree with the policy-pinned instance ID.

Hostname equality remains an additional defense but is no longer the primary VM
identity control.

## Recreated/clone VM protection

A newly created VM can reuse the same human-readable name after the original is
deleted. It receives a different immutable numeric GCE instance ID.

Because the instance ID is signed, policy-pinned and runtime-verified, an
attestation from the old VM fails closed on the replacement VM even if project,
zone and hostname are the same.

## Fail-closed behavior

Metadata timeout, redirect, missing Google metadata header, project/name/zone
mismatch, malformed instance ID, policy mismatch or artifact mismatch all keep:

```text
gateway_read_only_configuration_independently_attested = false
paper_order_submission_allowed = false
live_execution_allowed = false
real_money_trading_allowed = false
```

G2, the G0-G3 readiness bundle and the G0-G4 completion gate continue to call
the same signed-attestation verifier.

## Operator/reviewer sequence

1. Run the G7.6 handoff preflight on the approved VPS.
2. Record the GCE numeric instance ID reported by the live metadata-bound
   handoff.
3. Install the reviewed V2 root policy containing that instance ID.
4. The independent reviewer verifies Gateway/TWS Read-Only API configuration.
5. The reviewer signs a V2 artifact containing the exact same project and
   instance ID, off the trading VPS.
6. Install only the signed artifact on the VPS.
7. Run `python scripts/verify_gateway_readonly_attestation.py`.
8. Continue only if the verifier reports `VERIFIED`.

No broker order should be placed to prove any step above.


## G7.8 control-plane cross-binding

The reviewer handoff contract is upgraded to
`IBKR_GATEWAY_READ_ONLY_REVIEW_REQUEST_V2` with
`request_schema_version=2`. V2 includes the immutable
`g0_runtime_instance_id` from the G0/G1 control-plane proof. The handoff is
blocked unless that ID matches both the root policy and live GCE metadata.
