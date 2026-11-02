# AURORA G8.13 — Non-Executable Paper Adapter Source Review

G8.13 creates the first mainline Paper adapter **source-review** artifact after
the trusted G8.12 runtime prerequisite.

It does not implement a broker connector and does not import or execute IBKR
code.

## Input boundary

The source-review CLI consumes the trusted owner-only G8.12 artifact:

```text
runtime/aurora_g6_runtime_prerequisite/latest.json
```

The prerequisite must still be fresh and must exactly contain every G8.12
runtime check as passed. It must remain bound to the same:

- short-lived G5 human authorization;
- UUIDv4 evidence run;
- current Git SHA;
- immutable GCE instance ID;
- G0/G1 proof digest;
- G2 Paper Read-Only proof digest;
- independently signed Gateway/TWS Read-Only attestation digest;
- single sanitized Paper account fingerprint.

All implementation, connection, broker request, order object, Paper/LIVE and
real-money permission fields must remain false.

## Fixed review skeleton

The only candidate source reviewed by the installed CLI is:

```text
broker_engine/ibkr_paper_adapter_review_skeleton.py
```

The script verifies that the filesystem source is a regular, owner-controlled,
single-link, non-writable-by-group/world file and is byte-for-byte identical to
the blob tracked at `HEAD`.

The repository must be clean and the current Git SHA must equal the Git SHA
bound into G8.12.

## AST policy

The candidate source is parsed with Python AST and is never imported or
executed.

The policy permits only:

- one fixed `SKELETON_VERSION` constant;
- one class named `IBKRPaperAdapterReviewSkeleton`;
- the exact methods `__init__`, `describe`, `connect`,
  `materialize_order_request`, `submit_order`, `cancel_order`, and
  `modify_order`;
- an exact review-only description limited to PAPER,
  `127.0.0.1:4002`, `STK/LMT/DAY`;
- broker-facing methods whose entire body is one fixed `RuntimeError`.

The policy rejects imports, inheritance, decorators, async functions, extra
methods, default expressions, annotations, executable top-level statements,
dynamic calls/control flow, broker mutation attributes, credentials/raw account
scope expansion, market orders, short selling, fractional quantity support, or
any enabled execution permission.

## Passing status

A passing result is:

```text
SOURCE_POLICY_VALIDATED_NON_EXECUTABLE
```

and advances only to:

```text
INDEPENDENT_ADAPTER_SOURCE_REVIEW_REQUIRED
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

## Operator command

After G8.12 has produced a real trusted prerequisite on the approved VPS:

```bash
python scripts/g6_adapter_source_review.py
```

The trusted output is written to:

```text
runtime/aurora_g6_source_review/latest.json
```

through the existing atomic owner-only `0600` evidence writer.

## Relationship to legacy G6 drafts

Legacy PR #52 introduced the original static-source-policy idea but depended on
the pre-G8 G6.19 stack. It remains draft and is not release evidence.

G8.13 re-establishes the useful source-freeze concept directly on the current
G8.12 runtime/provenance boundary. Passing G8.13 does **not** authorize
implementation or an IBKR connection.
