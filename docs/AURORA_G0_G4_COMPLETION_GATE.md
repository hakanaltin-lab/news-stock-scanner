# AURORA V8.9.21 — G0-G4 Completion Gate

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

This means the infrastructure and complete pre-trade shadow chain have been
validated. It does **not** authorize a Paper broker order, automatic promotion,
LIVE execution, or real-money trading. Those flags remain false and the next
gate is explicitly recorded as `MANUAL_PAPER_ORDER_AUTHORIZATION_NOT_GRANTED`.
