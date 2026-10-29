#!/usr/bin/env bash
set -euo pipefail

REPO_URL="https://github.com/hakanaltin-lab/news-stock-scanner.git"
AURORA_HOME="${AURORA_HOME:-$HOME/aurora}"
REPO_DIR="$AURORA_HOME/news-stock-scanner"
VENV_DIR="$AURORA_HOME/venv"
CONFIG_DIR="$HOME/.config/aurora"
ENV_FILE="$CONFIG_DIR/ibkr-paper.env"

log() { printf '\n==> %s\n' "$*"; }
fail() { printf 'FAIL: %s\n' "$*" >&2; exit 1; }

[[ "$(id -u)" -ne 0 ]] || fail "Run as the normal OS Login user, not root."
command -v sudo >/dev/null 2>&1 || fail "sudo is required."

log "Install G2 OS dependencies"
sudo apt-get update
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y \
  ca-certificates \
  curl \
  dbus-x11 \
  git \
  jq \
  netcat-openbsd \
  python3 \
  python3-pip \
  python3-venv \
  tigervnc-common \
  tigervnc-standalone-server \
  tigervnc-tools \
  unzip \
  xfce4 \
  xfce4-terminal

log "Prepare AURORA workspace"
install -d -m 0755 "$AURORA_HOME"
install -d -m 0700 "$CONFIG_DIR"

if [[ -d "$REPO_DIR/.git" ]]; then
  git -C "$REPO_DIR" fetch origin main
  git -C "$REPO_DIR" checkout main
  git -C "$REPO_DIR" pull --ff-only origin main
else
  git clone --branch main --single-branch "$REPO_URL" "$REPO_DIR"
fi

log "Prepare isolated Python environment"
if [[ ! -x "$VENV_DIR/bin/python" ]]; then
  python3 -m venv "$VENV_DIR"
fi
"$VENV_DIR/bin/python" -m pip install --upgrade pip setuptools wheel

log "Prepare safe runtime environment"
if [[ ! -f "$ENV_FILE" ]]; then
  cat >"$ENV_FILE" <<'EOF'
AURORA_RUN_MODE=READ_ONLY
AURORA_IBKR_ENABLED=false
AURORA_IBKR_MODE=PAPER
AURORA_IBKR_HOST=127.0.0.1
AURORA_IBKR_PORT=4002
AURORA_IBKR_CLIENT_ID=82
AURORA_IBKR_TIMEOUT_SECONDS=8
AURORA_IBKR_PAPER_ACCOUNT_ALLOWLIST=
AURORA_IBKR_MARKET_DATA_ENABLED=false
AURORA_IBKR_MARKET_DATA_CLIENT_ID=83
AURORA_IBKR_MARKET_DATA_TIMEOUT_SECONDS=8
EOF
  chmod 600 "$ENV_FILE"
fi
chmod 600 "$ENV_FILE"

log "Prepare localhost-only TigerVNC startup"
install -d -m 0700 "$HOME/.vnc"
cat >"$HOME/.vnc/xstartup" <<'EOF'
#!/bin/sh
unset SESSION_MANAGER
unset DBUS_SESSION_BUS_ADDRESS
exec startxfce4
EOF
chmod 700 "$HOME/.vnc/xstartup"

log "Verify no broker/VNC port is publicly bound"
for port in 4002 5902; do
  if sudo ss -lntH | awk -v p=":$port" '
    $4 ~ p"$" && (
      $4 ~ /^0\.0\.0\.0:/ ||
      $4 ~ /^\[::\]:/ ||
      $4 ~ /^\*:/
    ) {found=1}
    END {exit !found}
  '; then
    fail "TCP/$port is publicly bound. Stop before continuing."
  fi
done

cat <<EOF

G2 VPS bootstrap complete.

Repository:
  $REPO_DIR

Python venv:
  $VENV_DIR

Runtime env:
  $ENV_FILE

Next:
  1. Run: vncpasswd
  2. Run: $REPO_DIR/scripts/start_aurora_vnc_local.sh
  3. Install/login to IB Gateway Paper manually inside the VNC session.
  4. Install the official IBKR TWS Python API using:
     $REPO_DIR/scripts/install_ibkr_official_api.sh <official-api-zip>
  5. Configure the Paper account runtime allowlist:
     $REPO_DIR/scripts/configure_aurora_g2_runtime.sh
  6. Run the G2 read-only proof:
     $REPO_DIR/scripts/run_aurora_g2_readonly.sh

LIVE trading: DISABLED
Paper order submission: DISABLED
EOF
