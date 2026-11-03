# AURORA G8.26 — IBKR Order Object Design Review Handoff

G8.26 is a **non-attesting** independent reviewer handoff for the frozen G8.25 design. It recomputes design validity against a fresh verified G8.24 attestation, and binds the design and upstream attestations by SHA-256.

The handoff emits an **unsigned** Ed25519 review template, with `decision=REVIEW_REQUIRED` and `signature_b64=null`. The operator does not approve its own design; an independent human reviewer must examine it, including Paper-only, transmit=false, and no broker object creation.

This feature does not import IBKR, create a Contract/Order, allocate order IDs, connect or send orders. Every Paper, LIVE, broker and real-money execution permission remains false.

Fixed runtime output: `runtime/aurora_g6_order_object_design_handoff/latest.json`.

Next gate: `SIGNED_INDEPENDENT_IBKR_ORDER_OBJECT_DESIGN_ATTESTATION_REQUIRED`.
