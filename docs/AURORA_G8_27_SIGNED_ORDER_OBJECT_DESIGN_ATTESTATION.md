# AURORA G8.27 — Signed Independent IBKR Order Object Design Review

A separately controlled Ed25519 public key and fixed reviewer policy are required to verify the G8.26 unsigned handoff. This gate independently recomputes the G8.25 non-executable design gate against a fresh G8.24 materializer attestation and requires exact SHA-256 bindings between the review request, upstream evidence, and signed reviewer artifact.

The reviewer must confirm the design remains Paper-only, transmit=false, non-executable, and free of broker object creation. A successful independent attestation advances **review state only**, not trading permission.

Trusted paths:
- `/etc/aurora/order-object-design-review-policy.json`
- `/etc/aurora/order-object-design-reviewer-ed25519.pem`
- `/var/lib/aurora/order-object-design-attestation/latest.json`

Sanitized runtime result: `runtime/aurora_g6_order_object_design_attestation/latest.json`.

No private signing key, IBKR client, Contract/Order object, network connection, Paper order or LIVE execution exists in this gate. All execution permissions remain false.

**Next gate:** `NON_EXECUTABLE_IBKR_ORDER_OBJECT_IMPLEMENTATION_CANDIDATE_REQUIRED`.
