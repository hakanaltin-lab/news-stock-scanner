# AURORA IBKR Paper read-only VPS acceptance procedure

**Scope:** Operator-run verification only. This procedure does not authorize orders, cloud resource creation, firewall changes, or a live-trading transition.

## Prerequisites

- Use only the existing approved VPS through authenticated SSH.
- Do not expose TCP 4002, 5902 or 6080 publicly.
- IB Gateway must be logged into the **Paper** account.
- API access must remain localhost-only on port 4002 and read-only.
- The official IBKR TWS Python API must be installed in the Python environment used by AURORA.
- Branch `aurora-g6-11-readonly-correlation` must be checked out with no unreviewed local modifications.
- The raw Paper account identifier must stay only on the VPS in a protected local file or protected environment variable. Do not paste it into GitHub or chat.

## One-time local account allowlist setup

The acceptance runner automatically creates the 256-bit HMAC evidence key on the VPS with mode `0600`. The only manual local secret preparation is the Paper account allowlist.

Create the protected directory and enter the Paper account identifier without echoing it to the terminal:

```bash
mkdir -p ~/.config/aurora
chmod 700 ~/.config/aurora
read -rsp "IBKR Paper account ID: " AURORA_PAPER_ACCOUNT
printf '\n'
printf '%s\n' "$AURORA_PAPER_ACCOUNT" > ~/.config/aurora/ibkr_paper_account_allowlist
unset AURORA_PAPER_ACCOUNT
chmod 600 ~/.config/aurora/ibkr_paper_account_allowlist
```

The file must remain owner-only. Never commit it.

## One-command acceptance run

From the checked-out repository:

```bash
python3 scripts/run_g6_11_readonly_acceptance.py
```

The runner performs these steps automatically:

1. Verifies the current Git commit and local VPS security prerequisites.
2. Creates or validates `~/.config/aurora/ibkr_evidence_hmac.key` as an exactly 256-bit hexadecimal key with mode `0600`.
3. Loads the Paper account allowlist without printing it.
4. Forces PAPER mode, localhost `127.0.0.1`, port `4002`.
5. Runs the existing IBKR read-only probe.
6. Captures only the whitelisted sanitized probe JSON.
7. Runs the offline acceptance validator.
8. Writes a sanitized evidence bundle under `runtime/g6_11_readonly_evidence/` with private file permissions.

The runner never enables order submission and never changes firewall rules.

## Successful result

A successful console result is:

`G6_11_READ_ONLY_EVIDENCE_CAPTURED`

The bundle still deliberately contains:

- `paper_order_submission_allowed=false`
- `live_trading_allowed=false`
- `release_approved=false`
- `evidence_authenticity_verified=false`
- `broker_session_independently_verified=false`

This means the evidence is ready for independent review; it is **not** an execution release.

## Sanitized evidence

The bundle may contain:

- current Git SHA;
- local security report;
- opaque `IBKR-EVID-XXXXXXXXXXXXXXXX` account evidence token;
- UTC snapshot timestamp;
- required callback completion flags;
- order-submission hard-block evidence;
- offline validation result.

It must not contain:

- raw IBKR account identifier;
- HMAC secret;
- credentials/passwords;
- account balances;
- raw broker errors containing sensitive identifiers.

The runner tests explicitly check that the raw account identifier and HMAC key do not appear in written evidence.

## Acceptance matrix

| Case | Expected result |
| --- | --- |
| Paper Gateway connected, localhost 4002, read-only, allowlisted identity, all required callbacks | `G6_11_READ_ONLY_EVIDENCE_CAPTURED` |
| Local VPS security prerequisites fail | BLOCKED before broker probe |
| Missing/insecure allowlist file | BLOCKED before broker probe |
| Missing HMAC key | Runner creates a new 256-bit local key with mode 0600 |
| Existing HMAC key has unsafe permissions or invalid format | BLOCKED before broker probe |
| LIVE mode / unsafe endpoint | Existing probe fails closed |
| Gateway disconnected | BLOCKED; no order |
| Required callback incomplete | BLOCKED; no order |
| Paper account identity mismatch | BLOCKED; no order |
| Probe exception or malformed output | Sanitized BLOCKED evidence; secrets are not exposed |

## Correlation evidence scope

The one-command runner proves a bounded **read-only snapshot** only. It does not prove order-to-execution correlation.

For G6.11 correlation acceptance, any existing Paper order used as evidence must separately map to broker-observed:

- permanent ID;
- client ID;
- order ID;
- verified Paper account identity;
- execution records where available.

**Do not place a new order merely to manufacture correlation evidence.** If no suitable existing Paper order exists, record that correlation item as `NOT TESTED`, not PASS.

## Security stop conditions

Stop the acceptance run and investigate if any of the following appears:

- a Live account;
- unexpected orders;
- exposed broker/VNC ports;
- raw credentials or account identifiers in output;
- mismatched account evidence;
- conflicting broker order identities.

Do not weaken read-only settings to make a test pass.

## Release gate

Before PR #42 or its dependent execution-safety PRs can move out of Draft, require:

1. current-head CI success;
2. independent code/security review;
3. a sanitized real Paper read-only evidence bundle from the approved VPS;
4. explicit disposition of any correlation cases that cannot be tested.

Even after a read-only PASS, Paper order submission and LIVE trading remain disabled until separately reviewed and explicitly authorized by a later execution release process.

**Go/no-go:** No Paper orders, no LIVE orders, and no production automation are authorized by this procedure.
