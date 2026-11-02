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
- unable to authorize LIVE trading or automatic promotion.

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


## G7.14 G4-to-G5 integration contract

The production G4 shadow-order object itself is now guaranteed to carry all
five fail-closed execution flags explicitly as `false`, including
`automatic_promotion_allowed` and `real_money_trading_allowed`.

A regression test feeds a real `evaluate_runtime_shadow(...)` nested
`shadow_order` directly into the G5 manual authorization gate. This prevents
test-only fixtures from drifting away from the actual G4 output contract.

A passing G5 result remains pre-execution only. No broker request, Paper order,
LIVE execution, automatic promotion or real-money trading permission is
created by this compatibility fix.
