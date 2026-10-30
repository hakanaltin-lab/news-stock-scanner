# AURORA V8.9.25 — G0-G4 Completion Gate

After the approved GCP bootstrap, manual IBKR Paper login/2FA, official TWS API
installation, and Paper account allowlist configuration, prepare one reviewed
shadow intent and run:

```bash
~/aurora/news-stock-scanner/scripts/run_aurora_completion_gate.sh \
  /protected/path/g4-intent.json BKR
```

The command validates the sanitized G0/G1 infrastructure proof, refreshes G2
Paper read-only and G3 real-time market-data evidence, creates one
broker-independent G4 shadow order, audits the persistent shadow ledger in
read-only mode, and writes the final status to:

```text
runtime/aurora_project_status/latest.json
```

The only passing status is:

```text
PAPER_RUNTIME_VALIDATED_SHADOW_ONLY
```

The completion gate recalculates the canonical SHA-256 digest of the current
G2/G3 readiness artifact and requires it to match the digest recorded by G4.
Missing, malformed, replayed, or mixed-run readiness evidence fails closed.
It also requires the G0/G1 digest recorded by readiness to match the current
sanitized infrastructure proof, preventing cross-run infrastructure evidence.
The read-only ledger audit also binds the exact current G4 receipt by canonical
SHA-256 digest; an audit of a valid but unrelated ledger record fails closed.

This means the infrastructure and complete pre-trade shadow chain have been
validated. It does **not** authorize a Paper broker order, automatic promotion,
LIVE execution, or real-money trading. Those flags remain false and the next
gate is explicitly recorded as `MANUAL_PAPER_ORDER_AUTHORIZATION_NOT_GRANTED`.
