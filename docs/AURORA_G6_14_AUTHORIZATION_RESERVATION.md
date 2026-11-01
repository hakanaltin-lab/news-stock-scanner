# AURORA G6.14 — Atomic Authorization Reservation Ledger

G6.14 adds persistent, local **at-most-once reservation** for a validated G6.13
Paper submission contract.

It remains completely non-executable. It does not import a broker API, create a
broker order object, call an order endpoint, or authorize Paper/LIVE trading.

## Why this gate exists

G6.13 validates that the reviewed authorization, risk artifact, intent and
shadow order belong together. A caller-supplied replay history is not sufficient
against concurrent processes or restarts.

G6.14 therefore persists a reservation in SQLite using `BEGIN IMMEDIATE` and
database uniqueness constraints.

A reservation is unique across:

- authorization ID;
- idempotency key;
- reviewed shadow-order SHA-256;
- G6.13 contract SHA-256.

Concurrent attempts to reserve the same logical order cannot all succeed.

## Contract freshness and self-integrity

Before any database mutation, G6.14 requires:

- `SUBMISSION_CONTRACT_VALIDATED_NON_EXECUTABLE`;
- the expected G6.13 contract version;
- all Paper/LIVE/broker permission flags false;
- canonical UUIDv4 authorization ID;
- valid SHA-256 intent, shadow and contract digests;
- valid idempotency key;
- a G6.13 contract no older than 30 seconds by default;
- recomputation of the G6.13 contract SHA-256 from the version, UTC generation
  time, authorization ID, intent digest, shadow digest and idempotency key.

Tampered or stale contracts never reach the persistence write.

## Successful reservation

A successful result is:

`AUTHORIZATION_RESERVED_NON_EXECUTABLE`

It still returns:

- `broker_submission_allowed=false`
- `paper_order_submission_allowed=false`
- `live_execution_allowed=false`
- `automatic_promotion_allowed=false`
- `real_money_trading_allowed=false`
- `broker_order_object_allowed=false`

The next gate is:

`PAPER_BROKER_ADAPTER_REVIEW_AND_FAILURE_SEMANTICS_REQUIRED`

## Critical limitation: reservation is not broker atomicity

SQLite can atomically reserve an authorization locally, but a future broker API
call would be an external side effect. There is no single ACID transaction that
can atomically commit both SQLite and IBKR.

Therefore G6.14 deliberately does **not** claim exactly-once broker execution.

A future Paper adapter must define fail-closed behavior for:

- process crash after reservation but before broker submission;
- broker timeout after a submission attempt;
- unknown/ambiguous broker acknowledgement;
- reconnect and order reconciliation;
- permanent order ID / client ID / order ID correlation;
- restart recovery;
- whether a reservation may ever be retried.

Until those semantics are separately implemented and reviewed, an uncertain
state must be treated as **do not retry automatically**.

## Persistence safety

The SQLite file is created with owner-only mode `0600`, synchronous writes are
set to `FULL`, and a write reservation uses `BEGIN IMMEDIATE`.

If the database is unavailable or a persistence operation fails, the result is
`LEDGER_UNAVAILABLE` with all submission permissions false.

## Dependency

This is a stacked development layer on top of G6.13 / PR #45, which is itself
stacked on G6.12 / PR #43. It must remain Draft while its dependencies are
unmerged.

G6.11 real operator-run IBKR Paper read-only VPS acceptance also remains an
independent release prerequisite.

No Paper or LIVE order is authorized by G6.14.
