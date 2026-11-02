# AURORA G8.17 — Independent Implementation-Design Review Handoff

G8.17 converts the validated G8.16 non-executable Paper adapter design into an
**unsigned, non-attesting** package for an independent human reviewer.

It does not approve the design itself and it does not enable implementation,
broker connectivity or orders.

## Revalidation before handoff

The installed command recomputes G8.16 from the trusted G8.15 source-attestation
evidence and the tracked design/source files. It does not trust an old
`design_validated=true` JSON string by itself.

The tracked G8.16 design digest must match the recomputed design result and all
implementation/execution permissions must remain false.

## Command

```bash
python scripts/g6_adapter_implementation_design_handoff.py
```

A successful result is written atomically to:

```text
runtime/aurora_g6_implementation_design_handoff/latest.json
```

## Review request

The handoff binds:

- G8.16 design-review artifact SHA-256;
- exact tracked design SHA-256;
- G8.15 source-attestation SHA-256;
- exact reviewed source SHA-256;
- G8.15 source-review UUID;
- source Git SHA;
- G8.13 skeleton version and adapter class.

The operator explicitly does **not** assert the design is safe.

## Unsigned template

The generated template remains:

```text
decision = REVIEW_REQUIRED
signature_b64 = null
reviewer_confirms_design_non_executable = null
reviewer_confirms_fail_closed_defaults = null
reviewer_confirms_no_credentials_or_raw_accounts = null
```

An independent reviewer must inspect the design and separately sign the next
attestation outside AURORA.

## Passing state

```text
status = READY_FOR_INDEPENDENT_IMPLEMENTATION_DESIGN_REVIEW
ready_for_independent_design_review = true
design_attestation_verified = false
next_gate = SIGNED_INDEPENDENT_ADAPTER_IMPLEMENTATION_DESIGN_ATTESTATION_REQUIRED
```

Even on PASS every implementation, broker and execution permission remains
false.

G8.17 therefore preserves the sequence:

```text
signed source review
→ frozen implementation design
→ independent design review
→ signed design attestation
→ only then consider an implementation candidate
```
