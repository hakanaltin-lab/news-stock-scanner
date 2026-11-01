# AURORA G6.16 — Persistent Monotonic Reconciliation Ledger

G6.16 persists the read-only reconciliation decisions produced by G6.15 so
restart, stale evidence or a later contradictory snapshot cannot silently
regress a broker state.

It remains non-executable and broker-independent.

## What is persisted

Each accepted reconciliation event stores:

- attempt ID;
- authorization ID;
- idempotency key;
- G6.13 contract SHA-256;
- G6.14 reservation receipt SHA-256;
- G6.15 reconciliation state and reason;
- evidence timestamp;
- broker permanent ID / client ID / order ID when observed;
- broker status;
- filled and remaining quantities;
- SHA-256 of the submission-attempt artifact;
- SHA-256 of the read-only broker observation;
- SHA-256 of the complete reconciliation event.

The ledger is append-only.

## Monotonicity rules

G6.16 rejects:

- evidence older than the latest persisted event;
- reuse of the same attempt ID with a different authorization/order identity;
- changes to an already-observed permId, clientId or orderId;
- disappearance of previously-observed broker identity;
- decreasing cumulative filled quantity;
- disappearance of prior fill evidence;
- invalid state transitions;
- changes after a terminal FILLED/CANCELLED/local-pre-dispatch state.

The exact same event is idempotent and is not inserted twice.

## Supported progression examples

A normal progression may look like:

`UNKNOWN → SUBMISSION_PENDING → OPEN → PARTIAL → CANCEL_PENDING → PARTIAL_CANCELLED`

or:

`OPEN → PARTIAL → FILLED`

Cancel-pending may return to OPEN/PARTIAL if later read-only evidence shows the
cancellation was not final. This does not permit an automated action; it only
records the newer broker observation.

## Terminal-state protection

The following states are immutable for the same attempt:

- `LOCAL_FAILURE_BEFORE_BROKER_DISPATCH`
- `BROKER_ORDER_CANCELLED_UNFILLED`
- `BROKER_ORDER_PARTIALLY_FILLED_CANCELLED`
- `BROKER_ORDER_FILLED`

A later stale or contradictory snapshot cannot change them.

## Persistence behavior

SQLite uses:

- `BEGIN IMMEDIATE`;
- `PRAGMA synchronous = FULL`;
- owner-only database permissions `0600`;
- unique event SHA-256 receipts.

Database failure returns `RECONCILIATION_LEDGER_UNAVAILABLE` and leaves all
execution permissions false.

## Safety invariants

Every G6.16 result keeps:

- `automatic_retry_allowed=false`
- `same_authorization_retry_allowed=false`
- `broker_submission_allowed=false`
- `paper_order_submission_allowed=false`
- `live_execution_allowed=false`
- `automatic_cancel_allowed=false`
- `automatic_modify_allowed=false`
- `broker_order_object_allowed=false`

G6.16 never imports IBKR and contains no place/cancel/modify call.

## Dependency

This PR is stacked on G6.15 / PR #47, which is stacked on PR #46, PR #45 and
PR #43.

G6.11 real operator-run IBKR Paper read-only VPS evidence remains mandatory
before any execution-release decision.

No Paper or LIVE order is authorized by G6.16.
