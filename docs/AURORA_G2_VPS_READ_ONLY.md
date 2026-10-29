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

G2 passes only if the existing probe returns:

```text
readiness = READY_FOR_PAPER_READ_ONLY
paper_order_submission_allowed = false
live_execution_allowed = false
```

The probe also requires managed account, account summary, positions and open
orders to complete successfully while the Paper account identity matches the
runtime allowlist.

## 8. Only after G2 PASS

The next runtime test is G3: verified real-time market data. G3 still does not
authorize Paper orders. Paper order submission remains a separate later gate.
