# AURORA V8.3 — IBKR Paper Read-Only Setup

This milestone connects AURORA to an Interactive Brokers paper session in
read-only mode. It does not submit orders and LIVE trading is hard-blocked.

## Safety state

- PAPER mode only
- LIVE trading hard-blocked in code
- No IBKR username/password is stored in GitHub
- Account identifiers are masked before they are written to AURORA output
- GitHub Actions keeps the connector disabled by default
- The first milestone is account/position/open-order visibility only

## IB Gateway settings

Use IB Gateway logged into the paper account.

For the default AURORA configuration:

- Host: 127.0.0.1
- Port: 4002
- Client ID: 82

In IB Gateway / TWS API settings:

1. Enable socket/API clients.
2. Confirm the socket port is 4002 for the paper Gateway session.
3. Keep API access read-only for this milestone.
4. If trusted-IP controls are enabled, allow only the local/VPS connection required by AURORA.

## Official Python API

Install the Python TWS API from Interactive Brokers official TWS API download
on the VPS that runs IB Gateway.

AURORA intentionally does not add an ibapi package from PyPI to requirements.txt,
because Interactive Brokers states that the supported API distribution comes
from its official TWS API package.

After installation, this command should import successfully on the VPS:

    python -c "from ibapi.client import EClient; from ibapi.wrapper import EWrapper; print('IBAPI OK')"

## Enable the AURORA paper probe

Set these environment variables on the VPS:

    export AURORA_IBKR_ENABLED=true
    export AURORA_IBKR_MODE=PAPER
    export AURORA_IBKR_HOST=127.0.0.1
    export AURORA_IBKR_PORT=4002
    export AURORA_IBKR_CLIENT_ID=82
    export AURORA_IBKR_TIMEOUT_SECONDS=8

Then run:

    python scripts/ibkr_paper_probe.py

Expected first successful milestone:

    readiness = READY_FOR_PAPER_READ_ONLY
    live_execution_allowed = false
    paper_order_submission_allowed = false

The probe should also return masked account information, account metrics,
positions and open orders.

## Next milestone

Only after the read-only probe passes do we add:

- paper order dry-run objects
- idempotency / duplicate-order protection
- stale-price and spread guards
- daily gross-order limits
- execution reconciliation
- explicit paper-order enable switch

LIVE order submission remains out of scope for V8.3.
