# AURORA G5 — Manual Paper Authorization Preflight

This gate is intentionally **pre-execution only**.

It validates that a human-created authorization artifact is:

- explicitly approved;
- restricted to `PAPER` mode;
- scoped to exactly one Paper order;
- short-lived (maximum 10 minutes by default);
- bound by SHA-256 to the exact G0-G4 completion artifact;
- bound by SHA-256 to the exact accepted G4 shadow order;
- identified by a canonical UUIDv4;
- unable to authorize any broker submission, Paper submission, LIVE trading,
  automatic promotion, or real-money trading;
- an exact V2 schema with no additional or missing fields.

A passing result is:

`MANUAL_PAPER_AUTHORIZATION_VALIDATED`

Even when it passes, all submission flags remain false:

- `broker_submission_allowed=false`
- `paper_order_submission_allowed=false`
- `live_execution_allowed=false`
- `automatic_promotion_allowed=false`
- `real_money_trading_allowed=false`

The next gate is `PAPER_EXECUTION_CONNECTOR_REVIEW_REQUIRED`.

This module does not import `ibapi`, does not create an IBKR order object,
does not call `placeOrder`, and cannot submit an order. It only proves that
the human approval evidence is narrow, current, and cryptographically bound
to the exact reviewed shadow intent.


## G7.15 G4-to-G5 integration contract

The production G4 shadow-order object itself is now guaranteed to carry all
five fail-closed execution flags explicitly as `false`, including
`automatic_promotion_allowed` and `real_money_trading_allowed`.

A regression test feeds a real `evaluate_runtime_shadow(...)` nested
`shadow_order` directly into the G5 manual authorization gate. This prevents
test-only fixtures from drifting away from the actual G4 output contract.

A passing G5 result remains pre-execution only. No broker request, Paper order,
LIVE execution, automatic promotion or real-money trading permission is
created by this compatibility fix.


## G7.16 exact shadow-order evidence binding

The G0-G4 completion gate now recomputes the persistent shadow-ledger payload
hash from the exact nested G4 `shadow_order`, its evidence digests and the
receipt timestamp. The receipt identity and payload hash must match that
recomputation.

Completion publishes `g4_shadow_order_sha256`. G5 independently recomputes
the SHA-256 of the exact shadow order presented for human authorization and
requires it to equal the completion binding. A valid completion generated for
one shadow order therefore cannot be paired with a different shadow order.

G5 validated output also carries the original authorization issue and expiry
timestamps so later non-executable gates can re-check that the human approval
has not expired.

All execution permission flags remain false.

## G8.10 trusted authorization artifact boundary

G8.10 upgrades the manual authorization schema to
`AURORA_G5_PAPER_AUTHORIZATION_V2`. The human authorization artifact must
contain exactly these safety fields as `false`:

- `broker_submission_allowed`
- `paper_order_submission_allowed`
- `live_execution_allowed`
- `automatic_promotion_allowed`
- `real_money_trading_allowed`

The human approval remains represented separately by `approved=true`; this
means only “the reviewed shadow order is approved for the next pre-execution
review gate.” It does **not** turn on Paper order submission.

The operational preflight is:

```bash
python scripts/g5_manual_authorization_preflight.py \
  --authorization /path/to/human-authorization.json
```

By default it reads the fixed trusted completion and G4 shadow artifacts and
writes:

```text
runtime/aurora_g5_authorization/latest.json
```

The completion artifact, G4 shadow artifact, and human authorization file must
all pass the trusted owner-only runtime JSON boundary: regular file, current
user owner, exact `0600` mode, one hard link, no symlink following, bounded
size, stable read, valid UTF-8 JSON, and no duplicate object keys. The output
is written atomically as owner-only `0600` evidence.

A successful CLI result is still
`MANUAL_PAPER_AUTHORIZATION_VALIDATED`, carries
`authorization_is_pre_execution_only=true`, and leaves every execution
permission false. Its next gate remains
`PAPER_EXECUTION_CONNECTOR_REVIEW_REQUIRED`.

## G8.11 full G0-G4 provenance binding

G5 no longer accepts a completion object merely because it says
`PAPER_RUNTIME_VALIDATED_SHADOW_ONLY`. The completion artifact must use the
expected completion-gate engine, contain the exact complete safety-check set,
and every required completion check must be `true`.

G5 independently validates the completion evidence-binding graph before
accepting a human authorization:

- readiness and G4 use the same canonical UUIDv4 evidence-run ID;
- the immutable GCE instance ID is well formed;
- the G0/G1 digest equals the digest recorded by readiness;
- the G2 Paper Read-Only digest equals the digest recorded by readiness;
- G2, runtime and readiness Gateway Read-Only attestation digests are equal;
- the readiness digest equals the digest recorded by G4;
- the exact reviewed shadow-order digest is bound;
- persisted and recomputed G4 ledger payload digests are equal;
- recorded and audited ledger-receipt digests are equal.

A successful G5 result publishes sanitized handoff identity for the later G6
review boundary:

- `authorization_version`;
- `authorization_artifact_sha256`;
- `evidence_run_id`;
- `gce_instance_id`;
- G0/G1, G2, Gateway-attestation, readiness, shadow-order and ledger-receipt
  SHA-256 bindings.

This lets a future broker-independent G6 review gate verify the exact human
authorization and exact runtime evidence chain without trusting a caller-
supplied summary. It still grants no execution permission.

