#!/usr/bin/env bash
set -euo pipefail

URL="https://download2.interactivebrokers.com/installers/ibgateway/stable-standalone/ibgateway-stable-standalone-linux-x64.sh"
DEST="${1:-$HOME/Downloads/ibgateway-stable-standalone-linux-x64.sh}"

mkdir -p "$(dirname "$DEST")"

curl --fail --location --proto '=https' --tlsv1.2 "$URL" -o "$DEST"
chmod 700 "$DEST"

echo "PASS: Official IB Gateway stable Linux installer downloaded."
echo "Installer: $DEST"
echo "SHA256:"
sha256sum "$DEST"

cat <<EOF

Run the installer only inside the localhost-only VNC desktop, for example:
  DISPLAY=:2 "$DEST"

After installation, log in manually to the IBKR PAPER account.
Do not store the IBKR password in scripts, GitHub, shell history, or env files.
EOF
