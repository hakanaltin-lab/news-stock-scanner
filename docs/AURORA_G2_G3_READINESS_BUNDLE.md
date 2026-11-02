# AURORA V8.9.27 — G0-bound G2/G3 Runtime Readiness Bundle

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

- the local sanitized G0/G1 infrastructure proof is verified, safe, and no
  more than 24 hours old;
- G2 is `READY_FOR_PAPER_READ_ONLY` with no required failure;
- both the G2 snapshot and readiness record state
  `gateway_read_only_configuration_independently_attested=true`;
- the G2 required-check list is complete, unique, and exactly matches the
  current readiness engine contract;
- the read-only connector still hard-blocks order submission;
- G2 evidence is no more than five minutes old;
- G2 and G3 carry the exact same valid deployed Git SHA;
- G2 and G3 runtime provenance binds to the same approved immutable GCE
  instance and the exact current G0/G1 proof digest;
- G3 uses a valid `PAPER`, `127.0.0.1:4002` configuration with a non-zero
  client ID and a verified Paper account;
- the G3 inherited broker-mutation surface is hard-blocked;
- G2 and G3 report the exact same sanitized Paper-account fingerprint set;
- the quote is explicitly `IBKR_REALTIME / REALTIME`;
- the execution-data gate passes;
- G3 evidence is no more than one minute old; and
- every Paper/live/broker submission flag remains false.

The sanitized result is written to:

```text
runtime/aurora_readiness/latest.json
```

The result records canonical SHA-256 digests of the exact G0/G1, G2 read-only,
and G3 market-data proofs used for the decision. The final completion gate must
match the G0/G1 digest, while G4 must match the G3 digest; missing, replayed, or
mixed-run evidence fails closed.
Missing or mismatched account fingerprints also fail closed, preventing G2
account/position evidence from being combined with G3 market data obtained
under a different allowlisted Paper account. Raw account IDs are never written.

The wrapper does not source the runtime env file. It accepts only approved
keys from the owner-only `0600`, single-link file, creates one fresh UUIDv4
evidence-run ID, and carries that same ID through strict G2 and G3. If strict
G2 fails, G3 is not attempted. The G3 proof is forced to its fixed trusted
runtime path and both G2/G3 proof files must pass the trusted evidence reader
before the bundle can evaluate them.

The wrapper still produces a fail-closed summary when G3 or the unified bundle
returns a non-zero status, then exits non-zero itself.

A connector-side `read_only=true` declaration cannot satisfy the independent
Gateway/TWS Read-Only attestation requirement. Missing, false, duplicated, or
incomplete G2 safety evidence fails closed.

Passing this bundle authorizes only the next **G4 controlled dry-run**. It does
not authorize a Paper broker order, real-money order, or automatic promotion.
