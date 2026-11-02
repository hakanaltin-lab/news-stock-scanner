# AURORA G8.21 — Signed Independent Implementation-Candidate Attestation

G8.21 verifies an independently signed human review of the exact hard-disabled
G8.19 implementation candidate handed off by G8.20.

A successful review still does not enable an IBKR connection or any order
operation.

## Separate candidate-review trust root

```text
/etc/aurora/adapter-candidate-review-policy.json
/etc/aurora/adapter-candidate-reviewer-ed25519.pem
/var/lib/aurora/adapter-candidate-review-attestation/latest.json
```

The reviewer private key must remain off the trading VPS.

## Signed binding

The G8.21 artifact binds:

- exact G8.20 candidate-review artifact SHA-256;
- exact G8.20 review-request SHA-256;
- exact tracked candidate source SHA-256;
- candidate version and class;
- G8.18 design-attestation SHA-256;
- G8.16 design SHA-256 and design-review UUID;
- G8.15 source-attestation SHA-256;
- bound source Git SHA.

The reviewer must confirm the candidate remains non-executable, all broker
methods are hard-disabled, and no broker imports exist.

## Verification

```bash
python scripts/verify_adapter_candidate_attestation.py
```

The sanitized result is written atomically to:

```text
runtime/aurora_g6_candidate_attestation/latest.json
```

## Passing state

```text
status = VERIFIED
adapter_candidate_independently_attested = true
next_gate = OFFLINE_ORDER_REQUEST_MATERIALIZER_DESIGN_REQUIRED
```

Every implementation, connection and execution permission remains false.
The next phase may therefore design a pure offline order-request materializer,
but still may not create an IBKR Order object or submit an order.
