# AURORA V8.9.5 — IBKR Paper Read-Only Proof

This milestone connects AURORA to an Interactive Brokers paper session in
read-only mode. It does not submit orders and LIVE trading is hard-blocked.

## Safety state

- PAPER mode only
- Fail-closed run modes: SAFE_OFF → READ_ONLY → DRY_RUN → PAPER_ENABLED
- IBKR endpoint restricted to 127.0.0.1:4002
- Managed account must match a runtime-only paper-account allowlist
- LIVE trading hard-blocked in code
- Every `placeOrder` call hard-blocked in the read-only connector
- No IBKR username/password is stored in GitHub
- Account identifiers are masked before they are written to AURORA output
- GitHub Actions keeps the connector disabled by default
- Invalid or misspelled broker modes fail closed
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
3. Keep the **Read-Only API** setting enabled for this milestone. IBKR states
   that this setting blocks API orders.
4. If trusted-IP controls are enabled, allow only the local/VPS connection required by AURORA.

IBKR's current defaults are 4002 for an IB Gateway paper session and 7497 for
a TWS paper session. AURORA uses IB Gateway port 4002 by default; if the
Gateway setting was changed, the configured port must match it.

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

    export AURORA_RUN_MODE=READ_ONLY
    export AURORA_IBKR_ENABLED=true
    export AURORA_IBKR_MODE=PAPER
    export AURORA_IBKR_HOST=127.0.0.1
    export AURORA_IBKR_PORT=4002
    export AURORA_IBKR_CLIENT_ID=82
    export AURORA_IBKR_TIMEOUT_SECONDS=8
    export AURORA_IBKR_PAPER_ACCOUNT_ALLOWLIST=<YOUR_PAPER_ACCOUNT_ID>

For the **pre-review** stage, use the dedicated operator runner from the
repository root instead of treating the expected unattested exit code as a
generic failure:

    bash scripts/run_aurora_g2_pre_review.sh

The runner creates a fresh UUIDv4 evidence-run ID, forces the fixed trusted G2
output path, verifies the runtime env file is a single-link owner-only 0600
regular file, parses only approved environment keys without sourcing shell
code, requires localhost Paper port 4002, and confirms that the Gateway is not
publicly bound.

The underlying probe is expected to exit with code `2` **before** independent
attestation. G8.5 accepts that exit code only when the newly generated evidence
has the exact same run ID and the V3 runtime-bound reviewer package proves:

- the real Paper diagnostic is otherwise clean;
- independent Gateway Read-Only attestation is the only required failure;
- Git SHA, immutable GCE instance ID and G0/G1 proof digest all match;
- all execution permissions remain false.

A successful G8.5 pre-review status advances only to human independent review.
It does not make G2 order-ready.

For low-level diagnostics, the probe can still be run directly:

    python scripts/ibkr_paper_probe.py

The module form is also supported:

    python -m scripts.ibkr_paper_probe

A successful broker diagnostic is not, by itself, G2 readiness. The connector
cannot independently attest the IB Gateway/TWS **Read-Only API** setting.

Before independent attestation is bound, an otherwise complete diagnostic is:

    readiness = NOT_READY
    diagnostic_read_only_ready = true
    next_milestone = INDEPENDENT_GATEWAY_READ_ONLY_ATTESTATION
    gateway_read_only_configuration_independently_attested = false

Only after separate operator/reviewer evidence confirms the Gateway/TWS Read-Only
API configuration may G2 reach:

    readiness = READY_FOR_PAPER_READ_ONLY
    gateway_read_only_configuration_independently_attested = true
    live_execution_allowed = false
    paper_order_submission_allowed = false

Do not use an environment variable or probe-supplied flag to self-attest this
control. AURORA intentionally ignores such a shortcut.

The probe should also return masked account information, account metrics,
positions and open orders. The raw paper account ID is used only for the
runtime allowlist comparison and must never be committed to GitHub or emitted
to logs/output.

Yahoo Finance 15-minute data is research-only in V8.9.5 and is explicitly
marked execution_eligible=false. Any future paper-order path must use a
separately validated real-time execution source such as IBKR real-time data.

The command exits with code `0` only when every required read-only check,
including independently bound Gateway/TWS Read-Only attestation, passes.
Disabled, incomplete, unattested, invalid-mode, missing-API and
connection-failure states exit with code `2`. The full sanitized proof is written atomically to:

    runtime/ibkr_paper_read_only/latest.json

For a service deployment, the output path can be overridden without changing
the repository:

    export AURORA_IBKR_PROBE_OUTPUT=/var/lib/aurora/ibkr/latest.json

## Post-review strict G2 proof

After the independent reviewer has inspected Gateway/TWS Read-Only API,
returned the signed artifact, and the production attestation verifier reports
`VERIFIED`, run:

    scripts/run_aurora_g2_readonly.sh

Only this post-review strict path may return a successful
`READY_FOR_PAPER_READ_ONLY` result. Paper and LIVE order submission remain
disabled.

## Next milestone

Only after the read-only probe passes do we add:

- paper order dry-run objects
- idempotency / duplicate-order protection
- stale-price and spread guards
- daily gross-order limits
- execution reconciliation
- explicit paper-order enable switch

LIVE order submission remains out of scope for V8.3.
