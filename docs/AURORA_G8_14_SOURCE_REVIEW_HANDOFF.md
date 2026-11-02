# AURORA G8.14 — Independent Adapter Source Review Handoff

G8.14 prepares the exact G8.13 Paper adapter review skeleton for an
**independent human source review**. It is a handoff step only.

It does not assert that the adapter source is safe, does not sign anything,
does not enable an IBKR connection and does not authorize a Paper or LIVE
order.

## Input

The installed handoff consumes the trusted G8.13 artifact:

```text
runtime/aurora_g6_source_review/latest.json
```

and independently rechecks the exact tracked source:

```text
broker_engine/ibkr_paper_adapter_review_skeleton.py
```

The repository must be clean and the source-review artifact Git SHA must equal
the current deployed Git SHA.

## Revalidation

Before a handoff can be produced, G8.14 requires:

- the exact G8.13 source-review schema;
- `SOURCE_POLICY_VALIDATED_NON_EXECUTABLE`;
- the source-review artifact to still require independent review;
- every implementation, broker connection and execution permission to remain
  false;
- the exact skeleton version and adapter class;
- source SHA-256 to equal the current tracked source bytes;
- source-policy SHA-256 to recompute exactly from the bound G8.13 policy
  payload;
- a valid short-lived G8.12 prerequisite digest;
- the exact Git SHA, G5 authorization ID, evidence-run ID, immutable GCE
  instance ID, G0/G1 digest, G2 Paper Read-Only digest, signed Gateway
  Read-Only attestation digest and one sanitized Paper-account fingerprint;
- fresh source-review evidence.

Any extra field, raw account ID, permission change, source modification,
digest mismatch, stale review, dirty repository or Git mismatch blocks the
handoff.

## Passing status is not approval

A passing result is:

```text
READY_FOR_INDEPENDENT_ADAPTER_SOURCE_REVIEW
```

The output deliberately states:

```text
source_policy_revalidated = true
source_attestation_verified = false
operator_asserts_source_safe = false
independent_source_review_required = true
signed_source_attestation_required = true
```

All execution permissions remain false.

The next gate is:

```text
SIGNED_INDEPENDENT_ADAPTER_SOURCE_ATTESTATION_REQUIRED
```

## Reviewer request

The handoff contains a sanitized `review_request` bound to:

- the exact G8.13 artifact digest;
- exact source SHA-256;
- exact source-policy SHA-256;
- exact runtime-prerequisite SHA-256;
- Git SHA;
- G5 authorization ID;
- evidence-run ID;
- immutable GCE instance ID;
- G0/G1, G2 and Gateway-attestation digests;
- sanitized Paper-account fingerprint.

The request explicitly includes:

```text
operator_asserts_source_safe = false
requires_human_source_review = true
signed_source_attestation_required = true
```

## Unsigned template

The `unsigned_attestation_template` is intentionally incomplete:

```text
decision = REVIEW_REQUIRED
review_id = null
reviewer_id = null
reviewer_confirms_source_non_executable = null
reviewer_confirms_scope_frozen = null
reviewer_evidence_sha256 = null
signature_b64 = null
```

AURORA does not fill those fields and does not possess the reviewer signing
key. The reviewer must inspect the exact source independently before any later
attestation may be created.

## Operator command

After a real G8.13 artifact exists on the approved VPS:

```bash
python scripts/g6_adapter_source_review_handoff.py
```

The owner-only trusted output is:

```text
runtime/aurora_g6_source_review_handoff/latest.json
```

## Safety boundary

Even when the handoff is ready:

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

G8.14 is administrative/review readiness only. It is not an adapter release.
