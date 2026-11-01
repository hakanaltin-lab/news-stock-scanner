# AURORA G6.18 — Paper Adapter Review Envelope

G6.18 creates a short-lived, broker-neutral review envelope from a persisted
G6.17 attempt that is still in `PREPARED_NON_EXECUTABLE`.

It is the last broker-independent representation before any future IBKR Paper
adapter implementation is reviewed.

## What G6.18 does

The builder opens the G6.17 SQLite journal in **read-only mode** and requires:

- canonical attempt UUID;
- latest event exactly `PREPARED_NON_EXECUTABLE`;
- no client ID / order ID / dispatch evidence yet;
- valid authorization, contract, reservation and intent digests;
- valid Paper account evidence token;
- PREPARED event time equal to registry prepared time;
- prepared age <= 30 seconds by default;
- canonical expected order JSON;
- expected-order SHA-256 recomputation;
- PREPARED event SHA-256 recomputation.

If the attempt has already recorded a dispatch claim or a local failure, a new
review envelope is not produced.

## Review envelope

The envelope contains:

- attempt ID;
- authorization ID;
- idempotency key;
- contract SHA-256;
- reservation receipt SHA-256;
- intent SHA-256;
- expected-order SHA-256;
- Paper account evidence token;
- symbol;
- BUY/SELL side;
- stock-only asset type;
- LMT order type;
- DAY time-in-force;
- whole-share quantity;
- limit price;
- generated UTC time;
- canonical review-envelope SHA-256.

## Explicit non-capabilities

Even when validated:

- `broker_submission_allowed=false`
- `paper_order_submission_allowed=false`
- `live_execution_allowed=false`
- `automatic_retry_allowed=false`
- `automatic_cancel_allowed=false`
- `automatic_modify_allowed=false`
- `broker_order_object_allowed=false`
- `broker_request_materialization_allowed=false`

G6.18 does not import IBKR and cannot construct or transmit a TWS API Order.

## Tamper resistance

The envelope builder independently verifies the persisted G6.17 registry and
PREPARED event.

Direct database modification of:

- expected order JSON;
- expected order SHA-256;
- event time;
- event SHA-256;
- identity/digest fields

causes fail-closed behavior.

## Lifecycle boundary

Envelope creation is allowed only while the attempt is PREPARED.

After either:

- `LOCAL_FAILURE_BEFORE_DISPATCH`, or
- `DISPATCH_CLAIM_RECORDED`

the review envelope gate closes for that attempt.

## Next gate

A passing result is:

`ADAPTER_REVIEW_ENVELOPE_VALIDATED_NON_EXECUTABLE`

and points only to:

`IBKR_PAPER_ADAPTER_IMPLEMENTATION_REVIEW_REQUIRED`

This is not approval to implement, enable, or run a write-enabled broker
adapter.

## Dependency

This PR is stacked on G6.17 / PR #49, then PR #48, PR #47, PR #46, PR #45 and
PR #43.

G6.11 real operator-run IBKR Paper read-only VPS evidence remains mandatory
before any execution release decision.

No Paper or LIVE order is authorized by G6.18.
