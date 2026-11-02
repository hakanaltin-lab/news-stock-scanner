# G6.21 IBKR Paper read-only operator acceptance (NO-GO until verified)

This checklist is for a human operator on the **existing approved VPS**. Offline CI and a synthetic CONNECTED JSON report are **not** proof of broker identity, IB Gateway Read-Only API settings, network isolation, or permission to submit orders.

## Preconditions (operator attestation; do not automate writes)
- [ ] Confirm the active IB Gateway login is the **Paper** account, not LIVE. Do not record raw account numbers or credentials.
- [ ] Inspect the **IB Gateway API configuration** and verify **Read-Only API** is enabled. The connector's literal `config.read_only=True` and `order_submission_hard_blocked=True` are **not independent Gateway evidence**.
- [ ] Confirm API listener is bound to loopback and Paper port **4002**; no public inbound 4002 or 5902 firewall exposure.
- [ ] Confirm local process, checked-out commit SHA, host alias, UTC time, and operator/reviewer identities without publishing secrets.
- [ ] Do not invoke placeOrder, cancelOrder, modify, retry, or any LIVE endpoint. Never create test orders to manufacture correlation evidence.

## Read-only evidence
- [ ] Run the existing G6.11 operator probe only after prerequisites are verified, using the documented secure secret injection procedure. Never paste `AURORA_IBKR_EVIDENCE_HMAC_KEY` into an issue, logs, shell history, or screenshots.
- [ ] Capture sanitized probe JSON and process exit code; remove raw account IDs, credentials, tokens other than approved non-reversible evidence token, and sensitive logs.
- [ ] Validate the sanitized report offline using `python3 scripts/paper_readonly_acceptance_validator.py <sanitized-report.json>`.
- [ ] Independent reviewer confirms Gateway Read-Only configuration evidence, Paper account identity, localhost binding, callback completeness, commit SHA, timestamp and absence of order submission.
- [ ] Link evidence to issue #44 and audit issue #53 via secure storage references, not secret material.

## Release decision
- **NO-GO** if any attestation, proof or review is missing.
- A passing offline validator means **diagnostic only**; it does not verify authenticity or authorize Paper orders.
- Paper order submission, LIVE execution, auto retry/cancel/modify and broker Order creation remain disabled until a separately reviewed and explicitly approved release gate.
