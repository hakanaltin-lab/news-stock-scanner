# AURORA G8.22 — Pure Offline Order-Request Materializer

G8.22 is the first functional order-intent transformation in the adapter path.

It remains completely offline and cannot create an IBKR request or Order
object.

## Supported preview contract

Only the following internal preview is supported:

- US-equity style uppercase symbol;
- side BUY or SELL;
- integer quantity only;
- positive decimal-string limit price with at most four decimals;
- order type LMT;
- time in force DAY;
- outside-RTH disabled;
- SELL must be reduce-only and must not exceed the supplied position quantity;
- BUY must not be marked reduce-only.

Raw account IDs and extra fields are rejected.

## G8.21 prerequisite

A current trusted G8.21 candidate-attestation result is mandatory:

```text
status = VERIFIED
adapter_candidate_independently_attested = true
next_gate = OFFLINE_ORDER_REQUEST_MATERIALIZER_DESIGN_REQUIRED
```

All G8.21 checks and execution permissions are independently revalidated before
an offline request preview can be created.

## Output safety

A successful preview explicitly records:

```text
paper_only = true
transmit = false
broker_request_materialized = false
broker_order_object_created = false
network_accessed = false
```

All broker and execution permissions remain false.

## CLI

Create an exact-schema JSON intent file, then run:

```bash
python scripts/build_offline_order_request_preview.py --intent-file /path/to/intent.json
```

The sanitized preview is written atomically to:

```text
runtime/aurora_g6_offline_order_request/latest.json
```

## Next gate

```text
INDEPENDENT_OFFLINE_ORDER_REQUEST_MATERIALIZER_REVIEW_REQUIRED
```

The offline materializer must be independently reviewed before any later phase
may consider translating this internal preview into an IBKR-specific object.
