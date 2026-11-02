# AURORA G8.18 — Signed Independent Adapter Implementation-Design Attestation

G8.18 verifies an **independently signed** human review of the exact G8.16
non-executable implementation design handed off by G8.17.

A successful signature does not enable implementation or orders. It only
advances the review state to a future non-executable implementation candidate.

## Separate design-review trust root

The design reviewer uses a trust root separate from the G8.15 source reviewer:

```text
/etc/aurora/adapter-design-review-policy.json
/etc/aurora/adapter-design-reviewer-ed25519.pem
/var/lib/aurora/adapter-design-review-attestation/latest.json
```

AURORA never creates the positive attestation and never stores the reviewer
private key.

## Policy

The root-controlled policy contains only:

```text
policy_version = 1
reviewer_id
public_key_sha256
expected_design_id
expected_skeleton_version
expected_adapter_class
max_attestation_age_seconds
allowed_clock_skew_seconds
```

## Signed design artifact

The signed payload binds:

- G8.17 design-review handoff artifact SHA-256;
- exact G8.17 review-request SHA-256;
- exact tracked G8.16 design SHA-256;
- G8.15 source-attestation SHA-256;
- exact reviewed source SHA-256;
- source-review UUID and source Git SHA;
- G8.13 skeleton version and adapter class.

The independent reviewer must positively confirm:

```text
reviewer_confirms_design_non_executable = true
reviewer_confirms_fail_closed_defaults = true
reviewer_confirms_no_credentials_or_raw_accounts = true
```

The design-review ID must be UUIDv4, the reviewer evidence digest must be a
non-zero SHA-256, and the detached signature must be Ed25519.

## Independent revalidation

A valid signature alone is insufficient.

G8.18 independently checks:

- exact artifact, policy, G8.17 handoff, request and G8.16 result schemas;
- root-controlled reviewer identity and public-key fingerprint;
- signature encoding and Ed25519 verification;
- capture/expiry policy;
- G8.17 remains explicitly non-attesting;
- all G8.16/G8.17 implementation and execution permissions remain false;
- design-review artifact digest and request digest are exact;
- tracked G8.16 design still matches the signed design SHA-256;
- tracked G8.13 skeleton source still matches the bound source SHA-256;
- design/source/skeleton/adapter identities match across every layer;
- repository is clean.

Any mismatch fails closed.

## Verification command

After the independent reviewer returns a signed artifact and the operator
installs it at the fixed path:

```bash
python scripts/verify_adapter_design_attestation.py
```

The sanitized result is written atomically to:

```text
runtime/aurora_g6_design_attestation/latest.json
```

## Passing state

```text
status = VERIFIED
adapter_design_independently_attested = true
next_gate = NON_EXECUTABLE_ADAPTER_IMPLEMENTATION_CANDIDATE_REQUIRED
```

Even on PASS:

```text
implementation_allowed = false
connection_allowed = false
broker_request_materialization_allowed = false
broker_order_object_allowed = false
automatic_retry_allowed = false
automatic_cancel_allowed = false
automatic_modify_allowed = false
broker_submission_allowed = false
paper_order_submission_allowed = false
live_execution_allowed = false
automatic_promotion_allowed = false
real_money_trading_allowed = false
```

A real PASS therefore authorizes **review progression only**, not broker code or
execution.
