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

The tool prints a **whitelisted** JSON report and exits with code 0 only when the snapshot is connected, all required callbacks complete, Paper identity is verified, exactly one sanitized Paper account fingerprint is present, the snapshot has a timezone-aware timestamp, and the order-submission hard block is present. Exit 1 indicates not ready or error; exit 2 indicates disabled/unsafe operator configuration. Neither permits an order.

## Acceptance evidence
Record the host alias (not public IP), Git commit, command exit code, and the sanitized JSON fields. The report includes `paper_account_fingerprint` in the form `IBKR-XXXXXXXXXX`, derived from a truncated SHA-256 digest, plus `snapshot_generated_at_utc`. These are intended to bind later diagnostic checks to the same Paper identity and snapshot time without exposing the raw IBKR account identifier.

Do not copy credentials, raw account identifiers, account balances, or broker error messages into GitHub issues or chat. A passing local probe proves only this particular read-only snapshot; it does **not** authenticate a saved JSON file by itself and does **not** prove reliable execution, order routing, profitability, or Live readiness.

The sanitized report can be checked offline with:

```bash
python3 scripts/paper_readonly_acceptance_validator.py sanitized_probe.json
```

A validator result of `READ_ONLY_SNAPSHOT_VALIDATED` confirms field consistency only. It deliberately keeps `evidence_authenticity_verified=false`, `broker_session_independently_verified=false`, `paper_order_submission_allowed=false`, `live_trading_allowed=false`, and `release_approved=false`.

## Acceptance matrix (record each case separately)
Run these checks only on the existing approved VPS, without altering public firewall rules, opening trading permissions, or using a Live account.

| Case | Expected outcome | Acceptance requirement |
| --- | --- | --- |
| Enabled Paper / localhost / port 4002, API in read-only mode | Exit 0 only with connected status, verified Paper identity, one sanitized account fingerprint, timezone-aware snapshot time, completed required requests and order hard-block evidence | Capture sanitized JSON, commit SHA and exit code; do not infer order readiness |
| Missing, malformed or multiple account fingerprints | Nonzero exit; no order | A single sanitized Paper identity is mandatory |
| Missing or timezone-naive snapshot timestamp | Nonzero exit; no order | Snapshot time must be explicit and timezone-aware |
| Probe disabled | Exit 2 / BLOCKED; no broker connection attempt | Must not silently enable |
| Mode LIVE, host not localhost, port 4001, or missing required environment variable | Exit 2 / BLOCKED; no broker connection attempt | Every unsafe/missing configuration blocks |
| IB Gateway unavailable / disconnected | Nonzero exit; no order | Connection failure is not readiness |
| Required callbacks incomplete, including executions | Nonzero exit; no order | A partial snapshot never passes |
| Paper identity unverified, unsafe endpoint, read-only proof missing or order hard-block missing | Nonzero exit; no order | Every individual safety requirement must pass |

**Evidence scope:** The read-only probe confirms connectivity and a bounded snapshot, not order-to-execution correlation. For G6.11 correlation acceptance, separately verify any existing Paper order mapping against broker-observed permanent ID, client ID, order ID, Paper account fingerprint and execution records. **Do not place a new order to generate test evidence.** If no existing orders are available, record correlation acceptance as NOT TESTED, not PASS.

**Security stop condition:** If unexpected orders, a Live account, exposed broker ports, credentials in output, mismatched account fingerprints or suspicious order identities are detected, stop the test, preserve only sanitized diagnostic evidence, and investigate before resuming. Do not change the broker to write-enabled mode to make a test pass.

## Release gate
A successful CI run alone is **not** an acceptance decision. Before moving PR #42 or dependent PR #43 out of Draft, require (1) current-head CI success, (2) independent code/security review, (3) sanitized real Paper read-only acceptance evidence from the approved VPS, and (4) documented disposition of any tests that cannot be executed (including unavailable order correlation evidence). An untested acceptance item must not be described as passed. Paper order submission and Live trading stay disabled, even after a read-only PASS, until separate explicit authorization and a different execution release process.

## Failure response
- Disabled or blocked: review environment variables and Paper-only endpoint; do not change to Live port 4001.
- Not installed: install only the official IBKR TWS API in the approved host environment.
- Incomplete snapshot: inspect Gateway session and API read-only settings locally; do not weaken safety gates.
- Invalid fingerprint or timestamp: treat the evidence as unusable; do not substitute a raw account number or hand-edit the report.
- Error: stop, investigate locally, and share only the sanitized report.

**Go/no-go:** No Paper orders, no Live orders, and no production automation until separately reviewed and approved.
