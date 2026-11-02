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

## G8.9 trusted ledger audit boundary

The read-only ledger verifier now requires the SQLite ledger itself to remain
a single-link, owner-only `0600` regular file and verifies that the inode does
not change while it is opened. Symlink, hardlink, wrong-owner or broad-mode
ledger files are blocked.

The G4 shadow input to the audit and the resulting
`ledger_audit.json` are also processed through the trusted runtime JSON
boundary. The audit report carries all broker/Paper/LIVE/automatic/real-money
permissions as false.
