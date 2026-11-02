# AURORA G7.17 — Fresh Paper State-Risk Preflight

G7.17 is a non-executable risk gate after the G5 manual Paper authorization preflight.

It does not submit, reserve, stage, or construct a broker order.

## Evidence contract

The gate accepts only the exact G2 Paper read-only proof, exact G0-G4 completion status, exact completion-bound G4 shadow order, and validated G5 human-authorization result.

The G2 SHA-256 must match the completion binding. The shadow SHA-256 must match both completion and G5. The G5 completion SHA-256 must match the exact completion object. Human authorization timestamps are rechecked and must still be current.

## Broker-state source

Portfolio state is not supplied by the caller. It is derived only from the fresh G2 read-only IBKR snapshot.

Required state includes READ_ONLY AURORA mode, Paper loopback endpoint 127.0.0.1:4002, hard-blocked order submission, independently verified Gateway/TWS Read-Only attestation, completed account-summary/position/open-order snapshots, and fresh G2 snapshot/readiness timestamps.

The caller cannot relax the default 60-second G2 freshness ceiling. An explicitly invalid reference clock blocks rather than falling back to wall time.

## Risk rules

For a BUY, the exact shadow order notional must be covered by the read-only AvailableFunds value. The readiness metric must match the raw snapshot value, and the snapshot currency must be USD.

For a SELL, AURORA does not assume short-selling capacity. Available inventory is current positive broker position minus already-open SELL quantity for the same stock. The requested quantity must fit inside that remainder.

Malformed positions/open orders, non-stock rows for the target symbol, non-finite quantities, stale state, evidence mismatch, non-USD funds, or expired human approval fail closed.

## Output

A passing status is PAPER_STATE_RISK_VALIDATED_NON_EXECUTABLE.

The next step is only ATOMIC_AUTHORIZATION_RESERVATION_REVIEW_REQUIRED.

The output exposes no broker account ID or cash/position amount. It reports boolean sufficiency results and evidence digests only.

All execution permissions remain explicitly false.
