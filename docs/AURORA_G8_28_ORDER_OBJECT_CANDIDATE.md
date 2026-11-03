# AURORA G8.28 — Hard-disabled IBKR Order Object Candidate

G8.28 introduces a tracked review-only skeleton for a future IBKR Contract/Order object materializer. Its source is parsed with Python AST and is **never imported or executed during review**. The static policy accepts only a frozen class, fixed literal metadata and six methods that unconditionally raise hard-block exceptions.

A current G8.27 independently signed design-verification runtime result is required before the candidate is considered reviewable. Local mock test evidence does not constitute a real independent human attestation.

Broker connection, contract creation, order creation, submission, cancellation, modification, IBKR imports, networking and LIVE trading remain disabled. All permissions remain false.

Review output: `runtime/aurora_g6_order_object_candidate/latest.json`.
Next gate: `INDEPENDENT_ORDER_OBJECT_CANDIDATE_REVIEW_REQUIRED`.
