# AURORA V8.9.22 — G2/G3 Runtime Readiness Bundle

This bundle runs after the manual IB Gateway **Paper Trading** login, 2FA,
official TWS API installation, and protected Paper account allowlist setup.
It does not submit an order.

From the AURORA VPS run:

```bash
~/aurora/news-stock-scanner/scripts/run_aurora_g2_g3_readiness.sh BKR
```

The wrapper executes the existing G2 read-only account/position/cash proof,
temporarily enables only the G3 market-data connector, requests one verified
real-time stock quote, and reconciles both evidence files.

The final status is `READY_FOR_CONTROLLED_DRY_RUN` only when:

- G2 is `READY_FOR_PAPER_READ_ONLY` with no required failure;
- the read-only connector still hard-blocks order submission;
- G2 evidence is no more than five minutes old;
- G3 uses `PAPER`, `127.0.0.1:4002`, and a verified Paper account;
- the quote is explicitly `IBKR_REALTIME / REALTIME`;
- the execution-data gate passes;
- G3 evidence is no more than one minute old; and
- every Paper/live/broker submission flag remains false.

The sanitized result is written to:

```text
runtime/aurora_readiness/latest.json
```

The result also records canonical SHA-256 digests of the exact G2 read-only
and G3 market-data proofs used for the decision. G4 must match the G3 digest
before it can create a shadow order; a missing or different proof fails closed.

The wrapper still produces this fail-closed summary when either probe returns a
non-zero status, then exits non-zero itself.

Passing this bundle authorizes only the next **G4 controlled dry-run**. It does
not authorize a Paper broker order, real-money order, or automatic promotion.
