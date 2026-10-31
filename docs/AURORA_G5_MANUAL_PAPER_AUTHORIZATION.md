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
