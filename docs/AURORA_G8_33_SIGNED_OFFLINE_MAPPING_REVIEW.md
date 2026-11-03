# AURORA G8.33 — Independently signed offline mapping review verifier

The G8.33 verifier authenticates a **separate human reviewer's Ed25519 signature** over G8.32's exact unsigned review request. It does not issue, approve or self-sign any artifact.

Production trust is rooted in protected fixed paths:
- `/etc/aurora/offline-mapping-review-policy.json`
- `/etc/aurora/offline-mapping-reviewer-ed25519.pem`
- `/var/lib/aurora/offline-mapping-review-attestation/latest.json`

Production offline evidence:
- `runtime/aurora_g6_offline_mapping_handoff/latest.json`
- `runtime/aurora_g6_offline_mapping/latest.json`
- `runtime/aurora_g6_offline_order_request/latest.json`
- `runtime/aurora_g6_order_object_candidate_attestation/latest.json`
- `config/ibkr_order_object_materializer_design_v1.json`

The verifier checks signature and reviewer identity, independently recomputes G8.31/G8.32 evidence and binds seven SHA-256 fields. It requires fresh timestamps, a trustworthy clean repo, explicit reviewer confirmations, and unchanged PAPER-only / transmit=false permissions. The CLI writes `runtime/aurora_g6_offline_mapping_attestation/latest.json`.

CI mocks the result of signature verification for positive *unit-test fixtures*; this is not evidence of an actual independent review. No IBKR SDK import, Contract/Order construction, network access, Paper order, LIVE order or real-money transaction is enabled.

Next research gate: `OFFLINE_IBKR_MAPPING_POST_ATTESTATION_RESEARCH_REQUIRED`.
