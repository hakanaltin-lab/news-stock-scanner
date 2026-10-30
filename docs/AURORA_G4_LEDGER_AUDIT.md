# AURORA V8.9.24 — G4 Shadow Ledger Audit

This read-only verifier checks the persistent G4 shadow ledger without changing
any receipt or contacting a broker.

Run on the AURORA VPS:

```bash
~/aurora/venv/bin/python \
  ~/aurora/news-stock-scanner/scripts/audit_aurora_g4_ledger.py
```

The audit passes as `LEDGER_VERIFIED` only when:

- SQLite's integrity check passes;
- the expected append-only receipt schema is present;
- every stored payload matches its SHA-256 digest;
- stored receipt fields match the embedded shadow record;
- every record is `SHADOW_ACCEPTED`;
- broker, Paper, and LIVE submission flags are false; and
- the readiness and market-data evidence digests are valid SHA-256 values.
- the exact receipt emitted by the current G4 artifact is present in the
  verified ledger, matched by a canonical SHA-256 binding.

The sanitized report is written atomically to:

```text
runtime/aurora_g4_shadow/ledger_audit.json
```

Missing, unreadable, malformed, altered, or unrelated receipts return
`BLOCKED`. The
verifier opens SQLite in read-only mode and exposes no insert, update, delete,
broker, Paper-order, or LIVE-order path.
