# AURORA G6.20 — Adapter Source Policy Review

G6.20 is the final broker-independent source gate before real Paper evidence is
bound to a future execution-release process.

It contains two components:

1. a hard-disabled IBKR Paper adapter **review skeleton**; and
2. an AST-based source policy that reviews the skeleton without executing it.

No IBKR API is imported and no broker request can be created or sent.

## Review skeleton

The only allowed class is:

`IBKRPaperAdapterReviewSkeleton`

Its interface is fixed to:

- `__init__`
- `describe`
- `connect`
- `materialize_order_request`
- `submit_order`
- `cancel_order`
- `modify_order`

The broker-facing methods must consist of a single hard-disabled
`RuntimeError`:

- `G6_20_CONNECTION_DISABLED`
- `G6_20_REQUEST_MATERIALIZATION_DISABLED`
- `G6_20_ORDER_SUBMISSION_DISABLED`
- `G6_20_ORDER_CANCELLATION_DISABLED`
- `G6_20_ORDER_MODIFICATION_DISABLED`

The `describe` method is restricted to PAPER / localhost:4002 / STK / LMT /
DAY and all execution permissions false.

## AST source policy

G6.20 parses source with Python `ast`. It never imports or executes the
candidate source.

The policy rejects:

- any import statement;
- extra classes;
- inheritance or decorators;
- extra methods;
- async methods;
- executable top-level statements;
- dynamic control flow not in the frozen skeleton;
- broker/network imports;
- broker mutation attributes;
- dynamic `eval` / `exec` / `compile` / `__import__` / file-open calls;
- any broker-facing method that is not exactly hard-disabled;
- any change to the skeleton version;
- any enabling of permissions in `describe`.

Source size is bounded and the exact source SHA-256 is recorded.

## G6.19 binding

The source policy requires a valid G6.19 implementation-review contract and
recomputes its canonical SHA-256.

It also requires the G6.19 release prerequisites to remain:

- real G6.11 Paper read-only evidence;
- independent source review;
- explicit Paper execution release;
- explicit LIVE execution release.

Removing any prerequisite blocks the source review.

## Passing result

A valid review produces:

`SOURCE_POLICY_VALIDATED_NON_EXECUTABLE`

and records:

- G6.19 review-contract SHA-256;
- exact source SHA-256;
- skeleton version;
- adapter class;
- release prerequisites;
- canonical source-policy SHA-256.

Even on PASS:

- `implementation_allowed=false`
- `connection_allowed=false`
- `broker_submission_allowed=false`
- `paper_order_submission_allowed=false`
- `live_execution_allowed=false`
- `automatic_retry_allowed=false`
- `automatic_cancel_allowed=false`
- `automatic_modify_allowed=false`
- `broker_order_object_allowed=false`
- `broker_request_materialization_allowed=false`

## Next gate

The next gate is intentionally not another theoretical broker adapter layer:

`G6_21_REAL_PAPER_EVIDENCE_BINDING_REQUIRED`

Before any write-capable Paper adapter is considered, the approved VPS must
produce the real G6.11 sanitized read-only evidence bundle.

## Dependency

This PR is stacked on G6.19 / PR #51 and the preceding safety stack.

No Paper or LIVE order is authorized by G6.20.
