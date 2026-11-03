# AURORA G8.32 — Unsigned offline IBKR mapping review handoff

G8.32 prepares independently reviewable evidence for G8.31's plain-dictionary mapping of a frozen PAPER-only LMT/DAY US equity preview. Its output is an **unsigned** Ed25519 reviewer template (`decision=REVIEW_REQUIRED`, `signature_b64=null`). Neither this code nor its CI unit fixtures provide a real human review.

The gate recomputes the exact mapping, checks the signed G8.30 review result and frozen G8.25 design digest, and binds the source request, result, and signed candidate attestation with SHA-256 digests. Crucially it also rejects G8.31 previews whose `candidate_attestation_sha256` does not match the actual G8.30 attestation hash.

No IBKR import, Contract/Order object, network connection, order ID allocation or submission is present or allowed. All execution flags remain **false**, including Paper and LIVE. Subsequent gate: `SIGNED_INDEPENDENT_OFFLINE_MAPPING_REVIEW_REQUIRED`.
