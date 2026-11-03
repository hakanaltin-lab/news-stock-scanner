# AURORA G8.29 — Non-attesting IBKR Order Object Candidate Review Handoff

This gate packages the G8.28 **hard-disabled, non-executable** candidate for independent source inspection. It re-evaluates the exact G8.28 candidate source with the G8.27 signed-design verification result, hashes the candidate, candidate-review evidence, and design-attestation result, and generates a canonical unsigned reviewer request.

The reviewer template defaults to `decision=REVIEW_REQUIRED`, `signature_b64=null`, and unconfirmed safety checks. No operator self-approval is possible within this gate. A distinct independent reviewer must inspect the exact source, and a later gate must validate their signed Ed25519 attestation.

Installed CLI reads only fixed local files:
- `broker_engine/ibkr_order_object_materializer_candidate.py`
- `runtime/aurora_g6_order_object_candidate/latest.json`
- `runtime/aurora_g6_order_object_design_attestation/latest.json`

Output: `runtime/aurora_g6_order_object_candidate_handoff/latest.json`.

**No broker/API import, Contract/Order object creation, Paper submission, LIVE trading, real money, signing key, or network connection is introduced.** All execution permissions remain false.

Next gate: `SIGNED_INDEPENDENT_ORDER_OBJECT_CANDIDATE_ATTESTATION_REQUIRED`.
