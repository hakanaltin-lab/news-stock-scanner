# AURORA G6.15 — Broker Failure & Reconciliation State Machine

G6.15 defines failure semantics for a future IBKR Paper submission adapter
without implementing that adapter.

It is **read-only and non-executable**. It does not import IBKR, submit, cancel,
modify, or retry broker orders.

## Purpose

A local G6.14 authorization reservation cannot prove what happened at IBKR after
a future adapter attempts a submission. Process crashes, timeouts and missing
acknowledgements create an ambiguity window where automatically retrying the
same logical order could create a duplicate.

G6.15 makes the default rule explicit:

> If a broker side effect might have happened and current read-only evidence
> cannot prove the outcome, do not retry automatically.

## Inputs

The state machine consumes:

1. a successful G6.14 reservation receipt;
2. an optional future submission-attempt artifact;
3. an optional normalized read-only broker observation.

A submission-attempt artifact is evidence only. G6.15 does not create it and
does not perform the submission.

The attempt must bind to the exact:

- authorization ID;
- idempotency key;
- G6.13 contract SHA-256;
- G6.14 reservation receipt SHA-256;
- expected symbol, side, quantity and limit price.

## Read-only broker observation

A broker observation must be explicitly:

- PAPER mode;
- read-only;
- LIVE disabled;
- order submission hard-blocked;
- snapshot verified;
- fresh (60 seconds maximum by default);
- associated with an opaque Paper account evidence token.

If an order is observed, G6.15 additionally requires positive permanent ID,
client ID, order ID, symbol, side, total quantity, limit price, fill quantities
and unique execution IDs.

If the attempt already recorded client/order IDs, the broker observation must
match them exactly.

## Current IBKR status semantics

G6.15 recognizes the current documented IBKR statuses:

- PendingSubmit
- PreSubmitted
- Submitted
- Filled
- PendingCancel
- PreCancelled
- Cancelled
- Inactive
- WarnState

Reference:
- https://ibkrcampus.com/docs/tws-api/ref/order-state
- https://ibkrcampus.com/docs/web-api/v1/endpoints/order-monitoring/order-status-value

Unknown future statuses are not guessed. They become manual-review states.

IBKR documents PendingSubmit as transmitted but not yet accepted by the
destination. PendingCancel and PreCancelled are also not final cancellation;
executions may still arrive. G6.15 therefore never treats these states as safe
for retry.

## State classes

Examples:

- `RESERVED_NO_SUBMISSION_ATTEMPT`
- `LOCAL_FAILURE_BEFORE_BROKER_DISPATCH`
- `BROKER_OUTCOME_UNKNOWN_DO_NOT_RETRY`
- `BROKER_SUBMISSION_PENDING`
- `BROKER_ORDER_OPEN_WORKING`
- `BROKER_ORDER_PARTIALLY_FILLED_WORKING`
- `BROKER_CANCEL_PENDING`
- `BROKER_ORDER_CANCELLED_UNFILLED`
- `BROKER_ORDER_PARTIALLY_FILLED_CANCELLED`
- `BROKER_ORDER_FILLED`
- `BROKER_ORDER_INACTIVE_MANUAL_REVIEW`
- `BROKER_WARNING_MANUAL_REVIEW`
- `BROKER_STATUS_UNKNOWN_MANUAL_REVIEW`

Contradictory identity, quantity, freshness or safety evidence is BLOCKED.

## Retry policy

Every result contains:

- `automatic_retry_allowed=false`
- `same_authorization_retry_allowed=false`
- `paper_order_submission_allowed=false`
- `live_execution_allowed=false`
- `automatic_cancel_allowed=false`
- `automatic_modify_allowed=false`
- `broker_order_object_allowed=false`

Even when a local pre-dispatch failure is proven, the already-reserved human
authorization cannot simply be reused. Any retry requires a new human
authorization under a future execution release process.

## Important absence rule

A read-only snapshot with no matching broker order is **not proof that no broker
side effect occurred** after a dispatched request. G6.15 classifies that case as
`BROKER_OUTCOME_UNKNOWN_DO_NOT_RETRY`.

Fresh broker evidence must be collected and manually reconciled.

## Dependency

This PR is stacked on G6.14 / PR #46. G6.14 is stacked on G6.13 / PR #45 and
G6.12 / PR #43.

G6.11 real operator-run IBKR Paper read-only VPS acceptance remains an
independent prerequisite before any execution release decision.

No Paper or LIVE order is authorized by G6.15.
