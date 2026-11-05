# AURORA G8.23 — Offline Materializer Independent Review Handoff

G8.23 creates the non-attesting handoff for independent review of the G8.22
offline order-request materializer.

It does **not** approve the materializer, sign an attestation, connect to a
broker, create an IBKR request or Order object, or permit Paper/LIVE execution.

## What is revalidated

The handoff independently rechecks:

- the exact G8.22 design contract;
- the tracked offline materializer source;
- the tracked bounded CLI source;
- exactly one synchronous top-level materializer entrypoint and exactly one
  synchronous top-level CLI entrypoint; duplicate overrides, async replacements
  and comment/string decoys do not satisfy the policy;
- absence of IBKR/network imports and broker mutation calls;
- the exact AST-level count of every offline safety marker, with every
  occurrence required to be the literal boolean `false` so duplicate text,
  comments or false-like values cannot mask an unsafe path;
- all execution permissions remain false.

The package binds SHA-256 digests of the design, materializer source and CLI
source into a canonical review request.

## Reviewer package

The generated template is intentionally unsigned and starts with:

```text
decision = REVIEW_REQUIRED
signature_b64 = null
```

A separate reviewer must independently confirm:

- offline-only behavior;
- no broker imports;
- no network path;
- fail-closed intent schema.

## Runtime output

```text
runtime/aurora_g6_offline_materializer_handoff/latest.json
```

## Next gate

```text
SIGNED_INDEPENDENT_OFFLINE_ORDER_REQUEST_MATERIALIZER_ATTESTATION_REQUIRED
```

All implementation, connection, broker object/materialization, submission,
Paper, LIVE, promotion and real-money permissions remain false.
