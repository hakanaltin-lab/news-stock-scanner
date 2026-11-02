# AURORA G8.19 — Non-Executable Adapter Implementation Candidate

G8.19 creates the first tracked **implementation candidate** after the G8.18
independent design attestation.

This is still not an operational broker adapter.

## Candidate source

The fixed candidate is:

```text
broker_engine/ibkr_paper_adapter_implementation_candidate.py
```

It has no imports and is never imported or executed by the G8.19 review gate.

Its broker-facing surface remains:

```text
connect
materialize_order_request
submit_order
cancel_order
modify_order
```

Every one of these methods raises a fixed G8.19 disabled error.

## Static AST policy

G8.19 parses the candidate as source text and requires:

- exactly two top-level identity constants;
- exactly one expected candidate class;
- an exact constructor and describe method;
- all five broker-facing methods hard-disabled;
- no Python imports;
- no IBKR broker API attributes such as `placeOrder`, `cancelOrder`,
  `reqGlobalCancel`, `exerciseOptions` or order-binding calls;
- no dynamic execution such as `eval`, `exec`, dynamic imports, lambda,
  comprehensions, try blocks or reflective attribute mutation;
- the fixed PAPER / loopback / LMT / DAY safety contract;
- every implementation and execution permission false.

## G8.18 binding

The candidate gate requires a current trusted G8.18 verification result:

```text
status = VERIFIED
adapter_design_independently_attested = true
next_gate = NON_EXECUTABLE_ADAPTER_IMPLEMENTATION_CANDIDATE_REQUIRED
```

The G8.18 result must have every verification check true and all permissions
false. Its design-review UUID, design-attestation digest, design digest,
source-attestation digest and source Git SHA are carried into the G8.19 review
result.

## Command

```bash
python scripts/g6_adapter_implementation_candidate_review.py
```

The sanitized result is written atomically to:

```text
runtime/aurora_g6_implementation_candidate/latest.json
```

## Passing state

```text
status = IMPLEMENTATION_CANDIDATE_VALIDATED_NON_EXECUTABLE
candidate_validated = true
design_attestation_verified = true
next_gate = INDEPENDENT_ADAPTER_IMPLEMENTATION_CANDIDATE_REVIEW_REQUIRED
```

A passing result still has every implementation, connection and execution
permission set to false.

G8.19 therefore moves from an approved design to a reviewable source candidate
without creating a working broker path.
