# AURORA V8.9.9 — G2 IBKR Paper Read-Only VPS Deployment

This milestone prepares the hardened AURORA VPS for a manually authenticated
IB Gateway Paper session and proves read-only API connectivity.

## Non-negotiable safety state

- LIVE trading remains unavailable.
- Paper order submission remains unavailable.
- IBKR API endpoint is `127.0.0.1:4002` only.
- VNC is `localhost` only on display `:2` / TCP `5902`.
- TCP/4002 and TCP/5902 are never opened publicly.
- IBKR username/password are never stored in GitHub, scripts, or env files.
- The Paper account ID exists only in the protected VPS runtime env.

## Why VNC is still required

Interactive Brokers currently documents that IB Gateway/TWS requires a GUI
login and that a headless session without a GUI is not supported. AURORA
therefore uses TigerVNC locally on the VPS only; access is carried through
the existing IAP SSH path rather than a public VNC firewall rule.

## 1. Bootstrap the VPS

Run after G0/G1 has passed:

```bash
cd ~/aurora/news-stock-scanner 2>/dev/null || true
curl -fsSL https://raw.githubusercontent.com/hakanaltin-lab/news-stock-scanner/main/scripts/bootstrap_aurora_g2_vps.sh -o /tmp/bootstrap_aurora_g2_vps.sh
bash /tmp/bootstrap_aurora_g2_vps.sh
```

The bootstrap installs only the OS/runtime tools needed for the read-only
milestone and creates a protected runtime env with broker access disabled.

## 2. Create the VNC password and start localhost-only VNC

```bash
vncpasswd
~/aurora/news-stock-scanner/scripts/start_aurora_vnc_local.sh
```

Expected listener:

```text
127.0.0.1:5902
```

Any wildcard/public `5902` listener is a hard failure.

## 3. Open the VNC tunnel from the local computer

Run on the local computer with Google Cloud CLI installed:

```bash
gcloud compute ssh aurora-trading-vps --project=project-ce9773ef-6814-469c-92b --zone=europe-west3-a --tunnel-through-iap -- -N -L 5902:localhost:5902
```

Then connect the local VNC Viewer to:

```text
127.0.0.1:5902
```

No Google Cloud firewall change for TCP/5902 is required or allowed.

## 4. Download and install IB Gateway Stable

On the VPS:

```bash
~/aurora/news-stock-scanner/scripts/download_ibgateway_stable.sh
```

The helper downloads the current official Interactive Brokers stable Linux
X86_64 installer from `download2.interactivebrokers.com`. It does not run the
installer automatically.

Inside the VNC desktop, launch the downloaded installer and complete the GUI
installation. After installation:

```bash
~/aurora/news-stock-scanner/scripts/launch_ibgateway_vnc.sh
```

Log in manually to the **Paper Trading** account. Do not save credentials in
AURORA scripts or environment files.

For G2, API socket access must be enabled and the Paper Gateway socket port
must be `4002`. Do not weaken any additional API safety setting automatically;
if the read-only probe cannot complete, stop and review the specific IBKR
setting rather than enabling trading capability.

## 5. Install the official IBKR Python TWS API

Interactive Brokers currently distributes the supported Mac/Unix API as
`twsapi_macunix.<version>.zip`. Download it from the official TWS API download
page after accepting the vendor terms, copy the ZIP to the VPS, then run:

```bash
~/aurora/news-stock-scanner/scripts/install_ibkr_official_api.sh ~/Downloads/twsapi_macunix.<version>.zip
```

The helper installs the locally downloaded official `pythonclient` into the
AURORA virtual environment. It intentionally does not run `pip install ibapi`
from a public package index.

## 6. Configure the runtime Paper account allowlist

```bash
~/aurora/news-stock-scanner/scripts/configure_aurora_g2_runtime.sh
```

The account input is hidden, validated, written with mode `0600`, and never
printed back to the terminal.

## 7. Run the G2 read-only proof

```bash
~/aurora/news-stock-scanner/scripts/run_aurora_g2_readonly.sh
```

The raw connector probe cannot self-certify the IB Gateway/TWS **Read-Only API**
setting. Even when all broker diagnostics pass, G2 remains blocked until that
external configuration has been independently reviewed and bound to the G2
evidence:

```text
diagnostic_read_only_ready = true
gateway_read_only_configuration_independently_attested = false
readiness = NOT_READY
next_milestone = INDEPENDENT_GATEWAY_READ_ONLY_ATTESTATION
```

The broker socket is allowed in exactly two read-only stages:

1. **PRE_REVIEW_DIAGNOSTIC** — only after trusted GCE/G0 identity and reviewer
   handoff are ready, solely to produce the fresh diagnostic proof required by
   the independent review package. Paper/LIVE submission remains false and the
   expected readiness is still `NOT_READY`.
2. **POST_REVIEW_PROBE** — only after the independently signed attestation is
   installed and the workflow reports `VERIFIED_FOR_G2_READ_ONLY_PROBE`.

While the workflow is waiting for the human reviewer, or any identity/handoff
condition is invalid, the probe must stop before opening the broker socket.

G2 passes only after the independently reviewed evidence is present:

```text
gateway_read_only_configuration_independently_attested = true
readiness = READY_FOR_PAPER_READ_ONLY
paper_order_submission_allowed = false
live_execution_allowed = false
```

Do not use an environment variable, connector flag, or order attempt as a
substitute for this attestation. The probe also requires managed account,
account summary, positions and open orders to complete successfully while the
Paper account identity matches the runtime allowlist.

## 8. Only after G2 PASS

The next runtime test is G3: verified real-time market data. G3 still does not
authorize Paper orders. Paper order submission remains a separate later gate.

## G8.1 read-only mutation-surface hardening

The runtime probe now treats broker mutation as a wider surface than order
placement alone. The IBKR snapshot client hard-blocks `placeOrder`,
`cancelOrder`, `reqGlobalCancel`, `exerciseOptions`, `replaceFA` and
`reqAutoOpenOrders` locally before any inherited EClient implementation can
run.

The probe also refuses IBKR `clientId=0` and observes open orders with
`reqAllOpenOrders()`, which does not associate returned orders with the
requesting API client. G2 readiness and the G0-G3 readiness bundle fail closed
unless these controls are present in fresh runtime evidence.

Every row in the complete open-order snapshot must report an explicit active
TWS status: `ApiPending`, `PendingSubmit`, `PreSubmitted`, `Submitted`, or
`PendingCancel`. Missing, terminal, or unknown statuses block read-only
readiness instead of being silently treated as active broker state.

Every open-order row must also identify a USD stock with a positive IBKR
`conId`, BUY/SELL direction and a positive finite quantity. A symbol may have
multiple open orders only when they identify the same contract; one symbol
mapping to multiple `conId` values, or one `conId` mapping to multiple symbols,
blocks readiness as ambiguous broker state.

For every open order, the non-binding `reqAllOpenOrders` observation must also
contain matching `orderStatus` callback evidence. Missing rows, orphan order
identifiers, status disagreement, invalid filled/remaining quantities or
non-identical duplicate callback rows block readiness. Identical duplicate
messages remain accepted because IBKR can emit them normally.

The two callbacks must bind the same positive account-wide `permId` and the
same non-negative source `clientId` in addition to the client-local `orderId`.
Duplicate `permId` values or duplicate `(clientId, orderId)` pairs block the
snapshot, while the same `orderId` from different clients remains distinct.

If `orderStatus` reports a non-zero filled quantity for an active order, the
snapshot must also contain matching `execDetails` evidence. Each execution is
bound to the same masked and verified Paper account, `permId`, source
`clientId`, client-local `orderId`, USD stock contract and BUY/SELL side. The
greatest reported cumulative quantity must equal `orderStatus.filled`; a
missing or mismatched execution account, or any orphaned, malformed or
contradictory execution row, fails closed. An explicit empty execution list is
accepted only when every active order reports zero filled quantity.

Every retained execution must also carry an exact integer `liquidation=0`.
Missing, boolean or non-zero values fail closed because they cannot prove that
the fill was free of an IB-initiated liquidation.

IBKR correction callbacks share the execution ID prefix before the final
period and differ only in the numeric revision after it. Rows in one correction
family must therefore be identical in every retained evidence field other than
that revision. Conflicting account, order, contract, side, quantity, price,
liquidation or time evidence inside one family blocks readiness, while distinct
execution families may advance cumulative fill quantity normally.

After correction-family deduplication, the sum of each distinct execution's
`shares` must equal both the greatest `cumQty` and `orderStatus.filled` within
floating-point tolerance. This blocks duplicated or missing fill rows that a
maximum-cumulative check alone could conceal.

The connector requests the current execution history with an empty,
read-only `ExecutionFilter` and a fixed request ID. Readiness requires the
matching `execDetailsEnd` callback before treating the execution snapshot as
complete, and rows delivered under any other request ID are ignored. The
downstream readiness gate independently requires every retained execution row
to carry that exact integer request ID; a missing, boolean or mismatched ID
fails closed even if upstream filtering regresses. A timeout, wrong completion
request ID or missing completion callback blocks the proof even if some
execution rows arrived. IB Gateway can return only the
execution history available under its configured trade-log window, so any
older partial fill that cannot be reconciled remains fail-closed.

These controls do not replace the independent Gateway/TWS Read-Only
attestation and do not authorize Paper or LIVE order submission.

## G8.4 trusted runtime evidence file

The G2 probe now writes its runtime proof through an atomic temporary file
with mode `0600`, flushes and fsyncs the file, replaces the target atomically,
verifies that the final target is the exact same regular-file inode, and fsyncs
the containing directory. Existing symlink or non-regular targets are rejected.

The installed reviewer-package loader accepts the fixed
`runtime/ibkr_paper_read_only/latest.json` only when it is:

- a regular file opened with no symlink following;
- owned by the current AURORA process user;
- exactly mode `0600`;
- a single-link file;
- no larger than 1 MiB;
- stable while being read;
- valid UTF-8 JSON with no duplicate object keys.

Any violation returns an empty proof and therefore blocks the independent-review
workflow. A pre-G8.4 evidence file with broader permissions must be regenerated
by the current probe. None of these controls authorizes Paper or LIVE orders.
