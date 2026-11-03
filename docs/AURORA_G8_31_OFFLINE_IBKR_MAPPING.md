# AURORA G8.31 — Offline IBKR field mapping research

This research gate is intentionally **not a broker adapter**. It turns a trusted G8.22 normalized preview into inspectable **plain Python dictionaries**, corresponding to the frozen G8.25 `Contract` and `Order` field mapping. All prices remain canonical USD decimal **strings**, not floats. Neither `ibapi` nor any other broker library is imported.

Inputs are exact schema G8.25 design, the trusted G8.30 independently signed candidate attestation result, and a normalized offline request. A missing or simulated production attestation blocks. Unit tests use artificial fixtures exclusively, not actual reviewer approvals.

Additional constraints: PAPER-only, port 4002 design, whole shares, LMT/DAY, outsideRth=false, transmit=false, no short sales or uncovered SELL orders, no secret/account data, no new permission flags.

Output is research data only. Even a valid result cannot instantiate `Contract` / `Order`, allocate an order ID, connect to a broker, or submit/cancel/modify orders.

Next gate: `INDEPENDENT_OFFLINE_IBKR_MAPPING_REVIEW_REQUIRED`.
