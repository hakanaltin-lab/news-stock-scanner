# AURORA G8.16 — Non-Executable Adapter Implementation Design

G8.16 defines the implementation boundary that may be reviewed **after** the
G8.15 independently signed adapter-source attestation verifies.

It is deliberately a design gate, not an implementation gate. No adapter code
is activated, no IBKR connection is opened, no broker request or order object
is materialized, and no order permission changes.

## Fixed design contract

The tracked contract is:

```text
config/ibkr_paper_adapter_implementation_design_v1.json
```

The contract freezes the first implementation scope to:

```text
broker mode = PAPER
endpoint = 127.0.0.1:4002
asset type = STK
order type = LMT
time in force = DAY
market orders = disabled
short selling = disabled
fractional quantity = disabled
credentials in adapter = disabled
raw account identifiers = disabled
```

The planned surface is limited to:

```text
connect
materialize_order_request
submit_order
cancel_order
modify_order
```

These names describe the future review surface only. G8.16 does not implement
them.

## G8.15 binding

The design gate requires a trusted G8.15 verification result showing:

```text
status = VERIFIED
adapter_source_independently_attested = true
next_gate = NON_EXECUTABLE_ADAPTER_IMPLEMENTATION_DESIGN_REVIEW_REQUIRED
```

The G8.15 result must still be within its signed validity window, every G8.15
verification check must be true, and every implementation/execution permission
must remain false.

The tracked G8.13 review skeleton is re-hashed and must still equal the
source SHA-256 bound into the signed G8.15 result. A changed skeleton blocks the
design gate even if an older source-attestation result exists.

## Command

After a valid G8.15 verification result exists at the trusted runtime-evidence
path, run:

```bash
python scripts/g6_adapter_implementation_design_review.py
```

The result is written atomically through the existing trusted runtime evidence
boundary to:

```text
runtime/aurora_g6_implementation_design/latest.json
```

## Passing state

A valid result is:

```text
status = DESIGN_VALIDATED_NON_EXECUTABLE
design_validated = true
source_attestation_verified = true
next_gate = INDEPENDENT_ADAPTER_IMPLEMENTATION_DESIGN_ATTESTATION_REQUIRED
```

A PASS still leaves all of these false:

```text
implementation_allowed
connection_allowed
broker_request_materialization_allowed
broker_order_object_allowed
automatic_retry_allowed
automatic_cancel_allowed
automatic_modify_allowed
broker_submission_allowed
paper_order_submission_allowed
live_execution_allowed
automatic_promotion_allowed
real_money_trading_allowed
```

## Why this gate exists

G8.15 proves that an independent reviewer approved the exact **non-executable
source skeleton**. That approval must not silently become permission to write or
activate broker code.

G8.16 therefore freezes the implementation design separately and requires a
new independent design-review attestation before any implementation permission
can be considered. This creates a clean separation between:

```text
source reviewed
→ design reviewed
→ implementation reviewed
→ Paper execution eligibility
```

No step automatically promotes to the next one.
