# AURORA G8.15 — Signed Independent Adapter Source Attestation

G8.15 verifies an **independently signed** review of the exact hard-disabled
Paper adapter source frozen by G8.13 and handed off by G8.14.

AURORA does not create the positive source-review attestation and does not hold
the reviewer signing secret.

## Separate trust root

Source review uses a trust root that is separate from the Gateway/TWS
Read-Only reviewer trust root.

Production paths are fixed:

```text
/etc/aurora/adapter-source-review-policy.json
/etc/aurora/adapter-source-reviewer-ed25519.pem
/var/lib/aurora/adapter-source-review-attestation/latest.json
```

The policy and reviewer public key must be root-controlled trusted files. The
signed attestation is verified with system OpenSSL Ed25519.

Environment variables and CLI arguments cannot redirect these production trust
paths.

## Policy schema

The source-review policy is exact and contains only:

```text
policy_version = 1
reviewer_id
public_key_sha256
expected_skeleton_version
expected_adapter_class
max_attestation_age_seconds
allowed_clock_skew_seconds
```

The expected source identity remains:

```text
skeleton_version = AURORA_G8_13_IBKR_PAPER_ADAPTER_REVIEW_SKELETON_V1
adapter_class = IBKRPaperAdapterReviewSkeleton
```

## Signed artifact schema

The independent reviewer signs the exact canonical JSON payload excluding only
`signature_b64`.

The signed V1 artifact contains:

```text
schema_version
attestation_type
review_id
decision
reviewer_id
captured_at_utc
expires_at_utc
git_sha
source_review_artifact_sha256
review_request_sha256
runtime_prerequisite_sha256
source_sha256
source_policy_sha256
skeleton_version
adapter_class
reviewer_confirms_source_non_executable
reviewer_confirms_scope_frozen
reviewer_evidence_sha256
signature_algorithm
signature_b64
```

A positive artifact requires:

```text
attestation_type = AURORA_IBKR_PAPER_ADAPTER_SOURCE_REVIEW_V1
decision = ATTESTED
signature_algorithm = ED25519
reviewer_confirms_source_non_executable = true
reviewer_confirms_scope_frozen = true
```

The review ID must be UUIDv4 and the evidence hash must be a valid non-zero
SHA-256.

## Independent revalidation

A valid signature is not sufficient by itself.

The verifier independently requires:

- the current repository to be clean;
- the current Git SHA to match the G8.13/G8.14 reviewed Git SHA;
- the fixed tracked skeleton bytes to match the signed source SHA-256;
- the trusted G8.13 source-review artifact digest to match G8.14 and the signed
  artifact;
- the G8.14 `review_request` to recompute to the exact signed
  `review_request_sha256`;
- the runtime prerequisite, source-policy, skeleton and adapter-class
  identities to match across G8.13, G8.14 and the signed artifact;
- G5 authorization ID, evidence-run ID, GCE instance ID, G0/G1 digest, G2
  Paper Read-Only digest, Gateway Read-Only attestation digest and sanitized
  Paper account fingerprint to remain internally consistent between G8.13 and
  G8.14;
- reviewer identity and public-key fingerprint to match the root-controlled
  policy;
- capture/expiry timestamps to satisfy the policy freshness and clock-skew
  limits;
- the detached Ed25519 signature to verify.

Any field-set expansion, raw-account injection, source change, Git mismatch,
dirty repository, digest mismatch, reviewer mismatch, expired review, invalid
signature or missing confirmation fails closed.

## Verification command

After the independent reviewer returns a signed artifact and the operator
installs it at the fixed path:

```bash
python scripts/verify_adapter_source_attestation.py
```

The sanitized verification result is also written through the trusted
owner-only evidence boundary to:

```text
runtime/aurora_g6_source_attestation/latest.json
```

## Passing status

A passing result is:

```text
status = VERIFIED
adapter_source_independently_attested = true
```

This confirms only the independent review of the frozen, non-executable source.

It advances to:

```text
NON_EXECUTABLE_ADAPTER_IMPLEMENTATION_DESIGN_REVIEW_REQUIRED
```

It does **not** enable implementation or execution.

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

A real passing artifact still requires an independent human reviewer and a
reviewer signature created outside AURORA.
