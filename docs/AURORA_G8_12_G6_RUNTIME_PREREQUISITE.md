# AURORA G8.12 — G6 Paper Connector Runtime Prerequisite

G8.12 is the broker-independent bridge between the trusted G5 human
authorization and any future Paper connector source review.

It does **not** implement, enable, connect, materialize or submit a broker
order.

## Why this gate exists

The earlier G6.12-G6.20 draft stack was built before the G8 runtime-evidence
hardening and before the trusted G5 V2 authorization contract. Those draft PRs
therefore remain draft and are not release evidence.

G8.12 establishes the mainline runtime prerequisite that a future rebased
connector review must consume.

## Inputs

The trusted CLI reads:

- `runtime/aurora_g5_authorization/latest.json`;
- `runtime/aurora_project_status/latest.json`;
- `runtime/aurora_g4_shadow/latest.json`;
- `runtime/ibkr_paper_read_only/latest.json`;
- the original trusted human authorization artifact passed with
  `--authorization`;
- the independently verified Gateway/TWS Read-Only attestation from the fixed
  production trust path.

Runtime JSON inputs use the existing owner-only trusted evidence reader.

## Independent revalidation

The gate does not trust G5 by label alone. It re-runs the human authorization
against the current trusted completion and exact reviewed shadow order, then
requires the immutable G5 fields to match the stored G5 result.

It also requires:

- the exact G2 proof SHA-256 recorded by G5;
- the exact same UUIDv4 evidence-run ID;
- the G2 process to have been explicitly in `READ_ONLY` run mode with Paper
  submission not requested and LIVE execution false;
- exact Paper connector configuration: enabled, `PAPER`, loopback
  `127.0.0.1:4002`, read-only, valid non-zero API client ID and valid timeout;
- verified GCE runtime provenance for the approved project, VM name, zone and
  the same immutable instance ID;
- the exact same canonical G0/G1 proof digest;
- the broker snapshot start, snapshot completion and readiness record to all
  be fresh and ordered within the bounded diagnostic window; missing, future,
  regressing or post-readiness completion evidence fails closed even when the
  snapshot contains no executions;
- G2 readiness to recompute as `READY_FOR_PAPER_READ_ONLY`;
- the recorded required G2 check map to exactly match the freshly recomputed
  required check map with every required check passing;
- exactly one verified sanitized Paper account fingerprint;
- the exact same signed Gateway Read-Only attestation in G2 and the runtime
  verifier;
- the attestation to bind the approved project, same Git SHA, GCE instance and
  G0/G1 proof.

## Passing status

A passing result is:

```text
READY_FOR_PAPER_CONNECTOR_SOURCE_REVIEW
```

This means only that connector **source review** may proceed.

All operational capabilities remain disabled:

```text
implementation_allowed = false
connection_allowed = false
broker_request_materialization_allowed = false
broker_order_object_allowed = false
automatic_retry_allowed = false
automatic_cancel_allowed = false
automatic_modify_allowed = false
broker_submission_allowed = false
paper_order_submission_allowed = false
live_execution_allowed = false
automatic_promotion_allowed = false
real_money_trading_allowed = false
```

The next gate is:

```text
REBASE_AND_REVIEW_BROKER_ADAPTER_SOURCE_AGAINST_G8_12
```

## Operator command

After a real G5 authorization has been validated:

```bash
python scripts/g6_runtime_prerequisite.py \
  --authorization /path/to/the/exact-human-authorization.json
```

The default output is:

```text
runtime/aurora_g6_runtime_prerequisite/latest.json
```

and is written through the same atomic owner-only `0600` evidence boundary.

## Critical boundary

A green CI run proves only offline gate behavior. A real passing artifact
requires the operator-run Paper runtime evidence and independently signed
Gateway/TWS Read-Only attestation on the approved VPS.

No old G6 draft PR is automatically approved or mergeable for release merely
because G8.12 passes.
