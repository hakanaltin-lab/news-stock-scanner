# AURORA — Broker Order Path Safety Audit (31 October 2026)

Status: REVIEW REQUIRED — no permission to place any order.

## Scope
Before enabling IBKR Paper order submission, audit **all** call sites that can reach EClient.placeOrder, broker connector submit_order methods, REST broker order endpoints, and indirect scheduling/automation paths. The read-only connector overriding placeOrder is not proof that another connector cannot place an order.

## Required evidence
1. Enumerate every order-capable entry point, its caller, environment guards, and effective broker account.
2. Test invalid/missing modes, non-paper account, remote IBKR host, port other than 4002, missing allowlist, stale market data, duplicate client order ID, and reconnect/retry scenarios. Each must fail closed.
3. Add CI assertions that production/live broker order submission is disabled in every run mode and that any Paper order path remains disabled until separately authorized.
4. Record independent, sanitized runtime evidence from the actual VPS IB Gateway Paper session; never include raw account identifiers or credentials.
5. Require explicit human approval for any transition from READ_ONLY to PAPER_ENABLED; do not infer approval from this audit.

## Acceptance
- Complete call graph and negative tests reviewed.
- G0–G4 evidence from one verified run, matched by correlation ID and account fingerprint.
- No external ports 4002/5902 exposed; no cloud resource changes.
- No real-money orders, no Paper orders, no automatic promotion.

This document is an audit checklist, not evidence that the tests passed.
