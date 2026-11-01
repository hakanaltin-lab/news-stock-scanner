# AURORA G6.19 — Paper Adapter Implementation Review Contract

G6.19 freezes the safety specification for any future IBKR Paper adapter.

It is a policy/review gate only. It does not import IBKR, connect to a broker,
construct an IBKR Order, materialize a broker request, submit, cancel, modify,
or retry an order.

## Inputs

G6.19 requires:

1. a fresh G6.18 review envelope; and
2. an exact declarative adapter implementation manifest.

The G6.18 envelope must be no older than 30 seconds by default. Its canonical
SHA-256 is recomputed before the manifest is evaluated.

## Frozen adapter manifest

A valid manifest is restricted to:

- Broker: `IBKR`
- API family: `TWS_API`
- Mode: `PAPER`
- Host: `127.0.0.1`
- Port: `4002`
- Explicit non-negative integer client ID
- Asset type: `STK`
- Order type: `LMT`
- Time in force: `DAY`

The following capabilities must remain disabled:

- fractional shares;
- short selling;
- market orders;
- automatic retry;
- automatic cancel;
- automatic modify;
- LIVE mode;
- LIVE port;
- credentials in repository;
- raw account IDs in artifacts;
- order submission implementation;
- broker Order object implementation;
- broker request materialization implementation.

The following gates must remain mandatory:

- source review;
- real G6.11 Paper read-only evidence;
- independent security review;
- explicit Paper execution release;
- explicit LIVE execution release.

The manifest schema is exact. Extra fields or missing fields are rejected.

## Output

A valid result is:

`IMPLEMENTATION_REVIEW_CONTRACT_VALIDATED_NON_EXECUTABLE`

It freezes:

- exact G6.18 review-envelope SHA-256;
- exact implementation-manifest SHA-256;
- attempt ID;
- authorization ID;
- idempotency key;
- Paper account evidence token;
- selected client ID;
- exact order shape;
- explicit release prerequisites;
- canonical G6.19 review-contract SHA-256.

## Explicit non-capabilities

Even when G6.19 passes:

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

A passing specification review is not permission to add a write-enabled adapter.

## Anti-expansion rules

G6.19 fails closed if a manifest attempts to introduce:

- port 4001;
- LIVE mode;
- MKT orders;
- GTC;
- futures/options/other asset types;
- fractional shares;
- short selling;
- automatic broker actions;
- request/order materialization;
- order submission;
- weaker evidence/review requirements.

## Next gate

G6.19 points only to:

`G6_20_ADAPTER_SOURCE_POLICY_REVIEW_REQUIRED`

That future gate may review source structure, but G6.11 real operator-run Paper
read-only evidence is still a release prerequisite.

## Dependency

This PR is stacked on G6.18 / PR #50, then PR #49, PR #48, PR #47, PR #46,
PR #45 and PR #43.

No Paper or LIVE order is authorized by G6.19.
