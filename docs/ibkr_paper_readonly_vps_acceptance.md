# AURORA IBKR Paper read-only VPS acceptance procedure

**Scope:** Operator-run verification only. This procedure does not authorize orders, cloud resource creation, firewall changes, or a live-trading transition.

## Prerequisites (confirm, do not assume)
- Existing approved VPS is running; use authenticated SSH. Do not expose TCP 4002 or 5902 to the internet.
- IB Gateway is logged into the **Paper** account; its API socket is restricted to localhost, port 4002. Configure IB Gateway read-only API mode.
- Official IBKR TWS Python API is installed on the same host, in the Python environment used for the probe.
- Repository branch `aurora-g6-11-readonly-correlation` is checked out, and no unreviewed changes are present.

## Operator-run command
Run from the repository root (the script also supports another working directory):

```bash
AURORA_IBKR_ENABLED=true \
AURORA_IBKR_MODE=PAPER \
AURORA_IBKR_HOST=127.0.0.1 \
AURORA_IBKR_PORT=4002 \
python3 scripts/ibkr_paper_readonly_probe.py
```

The tool prints a **whitelisted** JSON report and exits with code 0 only when the snapshot is connected, all required callbacks complete, Paper identity is verified, and the order-submission hard block is present. Exit 1 indicates not ready or error; exit 2 indicates disabled/unsafe operator configuration. Neither permits an order.

## Acceptance evidence
Record the UTC time, host alias (not public IP), Git commit, command exit code, and the sanitized JSON fields. Do not copy credentials, raw account identifiers, account balances, or broker error messages into GitHub issues or chat. A passing local probe proves only this particular read-only snapshot; it does **not** prove reliable execution, order routing, profitability, or Live readiness.

## Failure response
- Disabled or blocked: review environment variables and Paper-only endpoint; do not change to Live port 4001.
- Not installed: install only the official IBKR TWS API in the approved host environment.
- Incomplete snapshot: inspect Gateway session and API read-only settings locally; do not weaken safety gates.
- Error: stop, investigate locally, and share only the sanitized report.

**Go/no-go:** No Paper orders, no Live orders, and no production automation until separately reviewed and approved.
