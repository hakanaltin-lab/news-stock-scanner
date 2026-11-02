# AURORA V8.9.22 — G4 Runtime Shadow Gate

This package connects the fresh G2/G3 runtime evidence to the existing
broker-independent dry-run engine. It creates an auditable shadow order only.
It never submits an order to IBKR or any other broker.

Create an operator-reviewed intent JSON outside the repository:

```json
{
  "symbol": "BKR",
  "asset_type": "STK",
  "action": "BUY",
  "quantity": 1,
  "order_type": "LIMIT",
  "time_in_force": "DAY",
  "limit_price": 50.0,
  "risk_approval": "APPROVED",
  "idempotency_key": "operator-g4-unique-001"
}
```

The values above are structural examples, not a trade recommendation. On the
AURORA VPS, run the wrapper with the reviewed intent and the same symbol:

```bash
~/aurora/news-stock-scanner/scripts/run_aurora_g4_shadow.sh \
  /protected/path/g4-intent.json BKR
```

The wrapper first refreshes the G2 Paper read-only proof, G3 verified real-time
quote, and unified readiness decision. It then sets `DRY_RUN` only for the
broker-independent child process.

The shadow gate accepts only when:

- unified readiness is `READY_FOR_CONTROLLED_DRY_RUN` and at most 30 seconds old;
- the G3 market-data proof SHA-256 exactly matches the proof bound into the
  readiness decision;
- every readiness and market-proof submission flag is false;
- the intent symbol exactly matches the verified real-time quote symbol;
- the existing G4 risk, limit-order, spread, notional, short-sale, and market
  data controls all pass; and
- the result remains `SHADOW_ACCEPTED` with broker, Paper, LIVE, and automatic
  promotion flags false.

The result is written atomically to:

```text
runtime/aurora_g4_shadow/latest.json
```

Accepted shadow intents are also recorded in a private SQLite ledger:

```text
runtime/aurora_g4_shadow/shadow_audit.sqlite3
```

The idempotency key is a database primary key. A second process or later
restart using the same key fails closed as
`PERSISTENT_DUPLICATE_ORDER_INTENT`. The ledger exposes no update or delete
operation and is created with owner-only file permissions.

The record contains SHA-256 digests of the readiness and market-data evidence
used for the decision. Passing G4 requires operator review and does not
authorize a Paper broker order or real-money trading.

## G8.9 trusted G4 evidence boundary

G8.9 extends the owner-only runtime evidence boundary through the G4 shadow
stage. The readiness proof, G3 market-data proof and operator intent are read
only through the trusted JSON reader. The intent must be a current-user-owned,
single-link, non-symlink file with mode `0600`.

The accepted or blocked G4 result is written through the same atomic `0600`
writer used by G2/G3. A symlink or other unsafe output target fails closed.
The G4 top-level result now also carries
`real_money_trading_allowed=false` explicitly.

The persistent SQLite shadow ledger is created or reused only when it is a
current-user-owned regular file with mode `0600` and exactly one link.
Symlink/hardlink ledger paths are rejected before the ledger schema or shadow
record is written. These controls protect shadow evidence only and do not
authorize a broker order.
