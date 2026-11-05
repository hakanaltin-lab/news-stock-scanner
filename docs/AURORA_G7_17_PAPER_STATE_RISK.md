# AURORA G7.17 — Post-Authorization Fresh Paper State-Risk Preflight

G7.17 is a non-executable risk gate after the G5 manual Paper authorization preflight.

It does not submit, reserve, stage, or construct a broker order.

## Two-proof evidence model

The G2 proof embedded in G0-G4 completion remains the authorized provenance proof. Its SHA-256 must still match the completion binding.

A second G2 read-only probe is required after human authorization. This fresh proof supplies the broker state used for risk decisions. It is not allowed to replace or rewrite the authorized G2 provenance.

The fresh G2 proof must:

- be no older than the fixed 60-second ceiling;
- be captured after the G5 authorization was issued;
- use READ_ONLY AURORA mode and Paper loopback 127.0.0.1:4002;
- keep broker submission hard-blocked;
- contain a READY_FOR_PAPER_READ_ONLY result;
- carry the exact same independently verified signed Gateway/TWS attestation as the authorized G2 proof;
- carry the same verified Paper account fingerprint as the authorized G2 proof.

This avoids forcing a human to approve within 60 seconds of the original G2 snapshot while still ensuring that the risk calculation uses current broker state.

## Exact evidence bindings

The exact shadow SHA-256 must match both completion and G5. The G5 completion SHA-256 must match the exact completion object. Human authorization issue/expiry timestamps are rechecked and must still be current.

The caller cannot relax the 60-second fresh-G2 ceiling. An explicitly invalid reference clock blocks rather than falling back to wall time.

## Risk rules

For a BUY, the exact shadow order notional must be covered by AvailableFunds from the fresh G2 snapshot. The readiness metric must equal the raw snapshot value and the currency must be USD.

For a SELL, AURORA does not assume short-selling capacity. Available inventory is the current positive broker position minus already-open SELL quantity for the same stock. The requested quantity must fit inside that remainder.

Every position/open-order row used by the gate must belong to the verified Paper account. Malformed rows, non-stock rows for the target symbol, non-finite quantities, stale state, account or attestation drift, evidence mismatch, non-USD funds, or expired human approval fail closed.

Open-order identifiers must also be unique within the complete broker snapshot.
The account-wide `permId` and each `(clientId, orderId)` pair must be unique;
the same client-local `orderId` remains valid when it originates from different
clients and has a different `permId`. Duplicate broker-stable identities are
treated as ambiguous state and fail closed before any inventory or funds
decision.

Every open-order row must carry one of the explicit active TWS states `ApiPending`, `PendingSubmit`, `PreSubmitted`, `Submitted`, or `PendingCancel`. `PendingCancel` remains inventory-consuming because execution is still possible until cancellation is confirmed. Missing, terminal (`Filled`, `Cancelled`, `Inactive`, `ApiCancelled`), or unknown states are ambiguous in an active-order snapshot and fail closed; the gate never silently ignores them or treats them as safe inventory.

The full open-order snapshot, including orders unrelated to the reviewed symbol, must carry USD stock identity, a positive `conId`, BUY/SELL direction and positive finite quantity. Symbol-to-`conId` mappings must be one-to-one across distinct contracts, while multiple orders for the same symbol/contract remain valid. Any unrelated malformed or conflicting row blocks the complete broker-state proof rather than being ignored.

Each open order must also reconcile with the `orderStatus` callback snapshot by order ID, active status and filled/remaining quantity. Missing, orphaned or contradictory callback evidence blocks the risk proof; only exact duplicate status messages are tolerated.

Duplicate status callbacks must agree on `avgFillPrice`; filled orders require
a positive value and unfilled orders require zero.

Reconciliation also requires the same account-wide `permId` and source `clientId` on both callbacks. This prevents client-local order ID collisions from being merged into one broker-state observation.

An active order with a non-zero filled quantity must additionally reconcile
with `execDetails`. Execution identity, USD stock contract, side, positive
shares/price, the exact fixed integer execution request ID, masked Paper
account and cumulative quantity are validated. The execution account must
exactly match the open order's verified account, and the greatest cumulative
quantity must equal `orderStatus.filled`. Missing execution evidence, missing
or mismatched request/account identity, orphan callbacks, conflicting duplicate
execution IDs and partial-fill quantity drift all block the state-risk proof.
Every execution also requires a finite positive `avgPrice`; the row at the
greatest `cumQty` must match `orderStatus.avgFillPrice`. Missing, non-finite or
mismatched average-price evidence blocks the proof.
Each retained execution must additionally carry the exact integer
`liquidation=0`; missing, boolean or non-zero liquidation evidence blocks the
proof rather than accepting an IB-initiated liquidation as ordinary fill data.
It must also carry the exact boolean `pending_price_revision=false`; missing,
true or integer look-alike values block the proof so a provisional price is not
accepted as final execution evidence.

Execution IDs whose final period is followed by a numeric revision are treated
as one IBKR correction family. Every retained field other than that revision
must be identical across the family; contradictory correction callbacks fail
closed instead of competing through the maximum cumulative-quantity rule.
The deduplicated `shares` total must also equal both the greatest `cumQty` and
`orderStatus.filled`, so duplicated or incomplete execution rows cannot pass
through a matching cumulative maximum alone.

The fresh G2 proof must also show that the read-only execution request reached
its matching `execDetailsEnd` callback. Partial rows from a timed-out or
mismatched request are never treated as a complete execution snapshot.

## Output

A passing status is PAPER_STATE_RISK_VALIDATED_NON_EXECUTABLE.

The next step is only ATOMIC_AUTHORIZATION_RESERVATION_REVIEW_REQUIRED.

The output exposes no broker account ID or cash/position amount. It reports boolean sufficiency results and evidence digests only.

All execution permissions remain explicitly false.

## Main-branch G7 instrument-identity alignment

The fresh read-only position snapshot must identify every entry as a USD stock with a positive integer IBKR conId. Position symbols and conIds must be unique, with no silent aggregation across contracts. Missing, ambiguous, duplicated, or non-USD instrument identity blocks the state-risk gate. This is a non-executable, Draft-only integration until full CI and upstream review complete.
