# AURORA G8.20 — Independent Implementation-Candidate Review Handoff

G8.20 converts the G8.19 hard-disabled implementation candidate into an
unsigned, non-attesting package for an independent human code reviewer.

The candidate is still not imported, executed or connected to IBKR.

## Revalidation

Before handoff, G8.20 requires the exact G8.19 candidate-review result and
re-runs the candidate AST source policy. The tracked candidate SHA-256 must
match the G8.19 recorded digest.

Any broker-method enablement, import, dynamic execution, source change,
permission regression or malformed design/source binding blocks the handoff.

## Command

```bash
python scripts/g6_adapter_implementation_candidate_handoff.py
```

The sanitized output is written atomically to:

```text
runtime/aurora_g6_implementation_candidate_handoff/latest.json
```

## Unsigned review package

The request binds:

- G8.19 candidate-review artifact SHA-256;
- exact candidate source SHA-256;
- candidate version and class;
- G8.18 design-attestation SHA-256;
- G8.16 design SHA-256;
- G8.18 design-review UUID;
- G8.15 source-attestation SHA-256;
- bound source Git SHA.

The operator explicitly sets:

```text
operator_asserts_candidate_safe = false
```

The reviewer must independently confirm the candidate is non-executable, every
broker-facing method is hard-disabled, and no broker import exists.

## Passing state

```text
status = READY_FOR_INDEPENDENT_IMPLEMENTATION_CANDIDATE_REVIEW
candidate_attestation_verified = false
next_gate = SIGNED_INDEPENDENT_ADAPTER_IMPLEMENTATION_CANDIDATE_ATTESTATION_REQUIRED
```

All implementation and execution permissions remain false.
