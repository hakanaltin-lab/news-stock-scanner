# AURORA G8.25 — Non-Executable IBKR Order Object Materializer Design

G8.25 freezes the design contract for a future IBKR-specific Order/Contract
materializer. It consumes only a current verified G8.24 independent offline
materializer attestation.

This gate is design-only. It does not import `ibapi`, create a Contract or
Order object, allocate an order ID, resolve a contract, open a network
connection, or submit/cancel/modify an order.

## Frozen mapping

The design limits the future mapping to US equity Paper orders:

- Contract.symbol <- request.symbol
- Contract.secType = STK
- Contract.exchange = SMART
- Contract.currency = USD
- Order.action <- request.side
- Order.totalQuantity <- request.quantity
- Order.orderType = LMT
- Order.lmtPrice <- request.limit_price
- Order.tif = DAY
- Order.outsideRth = false
- Order.transmit = false

No raw account ID, credentials, market order, short sale, fractional quantity,
network access or order-ID allocation is allowed.

## Fixed runtime inputs

```text
runtime/aurora_g6_offline_materializer_attestation/latest.json
config/ibkr_order_object_materializer_design_v1.json
```

## Output

```text
runtime/aurora_g6_ibkr_order_object_design/latest.json
```

## Next gate

```text
INDEPENDENT_IBKR_ORDER_OBJECT_MATERIALIZER_DESIGN_ATTESTATION_REQUIRED
```

All implementation and execution permissions remain false.
