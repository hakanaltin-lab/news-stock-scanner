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
