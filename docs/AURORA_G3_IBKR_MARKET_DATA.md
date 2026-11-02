# AURORA V8.9.7 — G3 IBKR Real-Time Market Data Gate

This milestone adds an execution-grade market-data path from IB Gateway Paper.
It does not submit orders.

## Safety invariants

- PAPER endpoint only: `127.0.0.1:4002`
- Real Paper account must match the runtime allowlist
- Market-data connector is disabled by default
- Separate non-zero market-data client ID: `83`; client ID `0` is forbidden
- Invalid mode, port, client ID, or timeout values fail closed instead of
  falling back to a safe-looking default
- The connector hard-blocks broker mutation methods at the EClient boundary:
  `placeOrder`, `cancelOrder`, `reqGlobalCancel`, `exerciseOptions`,
  `replaceFA`, and `reqAutoOpenOrders`
- Market-data subscription cleanup (`cancelMktData` and
  `cancelTickByTickData`) is permitted because it only cancels data requests,
  not broker orders
- No `Order()` object or broker submission path exists
- Paper and LIVE order submission remain disabled

## IBKR data-type policy

IBKR identifies the market-data type returned by the API:

- `1` = Real-time
- `2` = Frozen
- `3` = Delayed
- `4` = Delayed frozen

AURORA accepts only `marketDataType=1` as execution-grade.

Delayed or frozen data may be useful for research or diagnostics, but they are
never execution eligible.

## Quote requirements

The snapshot must contain:

- valid bid > 0
- valid ask > 0
- ask >= bid
- valid last price > 0
- verified real-time market-data type

Only then may the connector emit:

```text
source = IBKR_REALTIME
execution_eligible = true
status = REALTIME_READY
```

Otherwise the output is fail-closed:

```text
status = NON_EXECUTION_DATA
execution_eligible = false
```

## Runtime configuration

Safe defaults:

```text
AURORA_IBKR_MARKET_DATA_ENABLED=false
AURORA_IBKR_MARKET_DATA_CLIENT_ID=83
AURORA_IBKR_MARKET_DATA_TIMEOUT_SECONDS=8
```

The common IBKR safety settings still apply:

```text
AURORA_IBKR_MODE=PAPER
AURORA_IBKR_HOST=127.0.0.1
AURORA_IBKR_PORT=4002
AURORA_IBKR_PAPER_ACCOUNT_ALLOWLIST=<PAPER_ACCOUNT_ID>
```

The real Paper account ID must exist only in the VPS runtime environment.

## Probe

After G2 Paper Read-Only has passed and IB Gateway is running:

```bash
export AURORA_IBKR_MARKET_DATA_ENABLED=true
python scripts/ibkr_market_data_probe.py NVDA
```

A successful G3 proof requires:

```text
snapshot_status = REALTIME_READY
market_data_type = REALTIME
execution_gate = PASS
execution_eligible = true
broker_submission_allowed = false
```

The sanitized proof is written atomically to:

```text
runtime/ibkr_market_data/latest.json
```

## Gate rule

G3 passes only when:

1. Paper account identity is verified.
2. Endpoint is exactly `127.0.0.1:4002`.
3. Market-data type is explicitly `1 / REALTIME`.
4. Bid, ask and last price are valid.
5. The generic execution market-data quality gate also passes.
6. The broker mutation surface is hard-blocked at the connector class
   boundary and client ID `0` is forbidden.
7. Invalid broker configuration fails closed before any API connection.
8. No broker-order object or submission path exists in the probe.

Passing G3 does not authorize Paper orders or real-money trading.

## G8.7 market-data connector hardening

G8.7 brings the G3 connector to the same fail-closed mutation boundary used by
G2. A market-data client that inherits Interactive Brokers' `EClient` can
otherwise inherit order-changing methods even when the application source
never calls them. AURORA therefore overrides the mutation methods locally and
raises before any inherited implementation can run.

Configuration parsing is also fail closed. Invalid numeric values are retained
as invalid sentinel values and cannot silently fall back to port 4002, client
ID 83, or timeout 8. The connector returns a blocked, not-attempted result
before network access when mode, port, client ID, or timeout validation fails.

These controls do not authorize Paper orders. They only make the real-time
market-data reader incapable of using the broker mutation surface.

