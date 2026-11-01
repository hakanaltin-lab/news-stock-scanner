# AURORA G6.13 — Hard-Disabled Paper Submission Contract

G6.13 is a broker-independent cross-check between already-reviewed artifacts.

It does **not** submit an order, create a broker order object, import IBKR APIs,
or grant Paper/LIVE execution permission.

## Inputs

The contract requires:

1. a successful G5 manual Paper authorization result;
2. a successful G6.12 portfolio-risk result;
3. the exact G6.12 order intent;
4. the exact G4 shadow order reviewed by the human authorization;
5. a supplied history of previously consumed authorization IDs.

## Cross-checks

The gate fails closed unless all of the following are true:

- G5 result is `MANUAL_PAPER_AUTHORIZATION_VALIDATED`;
- authorization is PAPER-only, one-order scoped, fresh, UUIDv4 identified,
  one-time consumable, and all submission flags remain false;
- the authorization ID is not present in the supplied replay history;
- G6.12 result is `VALIDATED_READ_ONLY` and still denies Paper/LIVE execution;
- the G6.12 `intent_sha256` matches an independently normalized digest of
  the exact intent;
- the idempotency key matches across intent and risk artifact;
- the exact shadow-order SHA-256 matches the digest stored by G5;
- shadow symbol, action, quantity, limit price and idempotency key match the
  G6.12 intent;
- shadow execution shape remains stock-only, LIMIT-only and DAY-only;
- all shadow submission flags remain false.

## Passing result

A passing result is:

`SUBMISSION_CONTRACT_VALIDATED_NON_EXECUTABLE`

Even on PASS:

- `broker_submission_allowed=false`
- `paper_order_submission_allowed=false`
- `live_execution_allowed=false`
- `automatic_promotion_allowed=false`
- `real_money_trading_allowed=false`
- `broker_order_object_allowed=false`

The authorization ID must still be atomically consumed by a separately reviewed
future adapter before any Paper submission could ever be considered.

The next gate is:

`PAPER_BROKER_ADAPTER_CODE_REVIEW_REQUIRED`

## Dependency

This is a stacked development layer on top of G6.12. It must not be merged or
used independently while G6.12 or G6.11 real read-only acceptance remains open.

## Release policy

G6.13 is not evidence of broker connectivity or execution readiness. It is an
offline artifact-integrity contract only. Real IBKR Paper read-only evidence,
independent review, replay-safe persistence, broker adapter review, explicit
Paper execution authorization, and separate LIVE release governance remain
mandatory.

No Paper or LIVE order is authorized by this gate.
