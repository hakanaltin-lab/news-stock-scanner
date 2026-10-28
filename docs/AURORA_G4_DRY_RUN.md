# AURORA V8.9.6 — G4 Dry-Run Execution Gate

V8.9.6 validates the complete pre-trade decision path without submitting any
order to Interactive Brokers or any other broker.

## Required runtime state

```text
AURORA_RUN_MODE=DRY_RUN
```

Any other run mode returns `BLOCKED / DRY_RUN_MODE_REQUIRED`.

## Accepted order-intent profile

A shadow order is accepted only when all controls pass:

- asset type = `STK`
- action = `BUY` or `SELL`
- order type = `LIMIT`
- time in force = `DAY`
- quantity > 0
- limit price > 0
- `risk_approval=APPROVED`
- explicit idempotency key is present
- SELL quantity does not exceed current long position
- execution market-data gate passes
- source is execution-grade (`IBKR_REALTIME`)
- market timestamp is fresh
- bid/ask are valid
- spread is within the configured threshold
- order notional is within the configured threshold
- projected daily gross notional is within the configured threshold

## Default limits

```text
AURORA_DRY_RUN_MAX_ORDER_NOTIONAL_USD=100
AURORA_DRY_RUN_MAX_DAILY_GROSS_NOTIONAL_USD=500
AURORA_DRY_RUN_MAX_SPREAD_BPS=50
```

These are safety-test limits, not investment sizing recommendations.

## Output

A valid dry-run intent returns:

```text
status = SHADOW_ACCEPTED
broker_submission_allowed = false
paper_order_submission_allowed = false
live_execution_allowed = false
```

The engine has no broker dependency. Its explicit `submit_to_broker()` method
always raises:

```text
DRY_RUN_BROKER_SUBMISSION_HARD_BLOCKED
```

## Duplicate protection

Every order intent must provide an `idempotency_key`. Once accepted in the
current engine state, reuse of the same key is blocked as
`DUPLICATE_ORDER_INTENT`.

Persistent restart-safe idempotency and broker reconciliation belong to a
later execution milestone and are not claimed by V8.9.6.

## Gate rule

G4 passes only when the offline CI suite proves:

1. SAFE_OFF cannot create a shadow order.
2. Valid DRY_RUN intent creates only SHADOW_ACCEPTED.
3. Market orders are rejected.
4. Options/non-stock assets are rejected.
5. Short selling is rejected.
6. Stale and research-only market data are rejected.
7. Excess spread is rejected.
8. Per-order notional limit is enforced.
9. Daily gross notional limit is enforced.
10. Duplicate idempotency keys are rejected.
11. Broker submission remains hard-blocked.

Passing G4 does not authorize Paper broker orders and does not authorize
real-money trading.
