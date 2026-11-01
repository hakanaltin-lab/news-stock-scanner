# AURORA G6.17 — Trusted Submission Attempt Journal

G6.17 replaces a caller-supplied submission-attempt JSON with a persistent,
append-only attempt lifecycle journal.

It does **not** connect to IBKR, create a broker order object, submit an order,
cancel an order, modify an order, or retry an order.

## Trust boundary

A G6.17 attempt cannot be prepared from JSON alone.

Before creating an attempt, the journal requires:

1. a successful G6.14 reservation artifact;
2. the exact G6.13 submission contract;
3. the exact six-field G6.12 intent;
4. an opaque Paper account evidence token;
5. the actual G6.14 SQLite reservation ledger.

The journal opens the G6.14 database read-only and verifies:

- authorization ID;
- idempotency key;
- intent SHA-256;
- shadow-order SHA-256;
- contract SHA-256 and version;
- contract generation time;
- reservation state;
- reservation timestamp;
- reservation receipt SHA-256.

The reservation receipt is recomputed from the persisted database row. A
fabricated JSON reservation with no matching persisted row is rejected.

## Attempt lifecycle

The immutable registry is created once per authorization/order identity.

Lifecycle events are append-only:

- `PREPARED_NON_EXECUTABLE`
- `LOCAL_FAILURE_BEFORE_DISPATCH`
- `DISPATCH_CLAIM_RECORDED`

A prepared attempt alone is **not** a G6.15 submission-attempt artifact.

Only one final boundary event may follow PREPARED.

### Local failure

`LOCAL_FAILURE_BEFORE_DISPATCH` means the future adapter recorded evidence
that it failed before crossing its broker-dispatch boundary.

Even then:

- the consumed authorization is not reused;
- automatic retry remains false;
- any future retry requires a new human authorization.

### Dispatch claim

`DISPATCH_CLAIM_RECORDED` stores:

- client ID;
- order ID;
- a SHA-256 digest of future adapter dispatch-boundary evidence;
- event time.

This is intentionally called a **claim**. It does not prove that IBKR accepted,
received, routed, or executed an order.

G6.15 must still use fresh read-only broker evidence. Without matching broker
evidence, the result remains:

`BROKER_OUTCOME_UNKNOWN_DO_NOT_RETRY`

## Race safety

SQLite uses `BEGIN IMMEDIATE` and uniqueness constraints.

This prevents:

- two attempt IDs for the same authorization;
- two attempts for the same idempotency key;
- both LOCAL_FAILURE and DISPATCH_CLAIM winning concurrently;
- silent reuse after restart.

An exact repeated final event is idempotent and returns the existing normalized
attempt artifact.

## Normalized G6.15 artifact

A finalized journal event produces the exact fields G6.15 needs:

- attempt ID;
- Paper mode;
- attempt time;
- authorization ID;
- idempotency key;
- G6.13 contract SHA-256;
- G6.14 reservation receipt SHA-256;
- dispatched/local-failure flags;
- expected symbol, side, quantity and limit price;
- client ID/order ID when a dispatch claim exists;
- Paper account evidence token;
- journal event SHA-256.

All execution/retry flags remain false.

## Safety invariants

Every journal result keeps:

- `broker_submission_allowed=false`
- `paper_order_submission_allowed=false`
- `live_execution_allowed=false`
- `automatic_retry_allowed=false`
- `same_authorization_retry_allowed=false`
- `automatic_cancel_allowed=false`
- `automatic_modify_allowed=false`
- `broker_order_object_allowed=false`

## Dependency

This PR is stacked on G6.16 / PR #48, then G6.15 / PR #47, PR #46, PR #45 and
PR #43.

G6.11 real operator-run IBKR Paper read-only VPS evidence remains mandatory
before any execution release decision.

G6.17 still does not implement a broker adapter. No Paper or LIVE order is
authorized.
