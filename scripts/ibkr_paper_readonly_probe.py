"""Operator-invoked IBKR Paper connectivity probe. No orders or secrets printed.

Run only on the IB Gateway host. Connector itself hard-blocks placeOrder.
"""
import json
import os
import sys
from datetime import datetime
from pathlib import Path

# Allow direct execution from any working directory on the Gateway VPS.
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from engines.ibkr_gateway_connector import get_ibkr_read_only_snapshot


def _valid_fingerprint(value):
    return (isinstance(value, str) and value.startswith("IBKR-")
            and len(value) == 15
            and all(c in "0123456789ABCDEF" for c in value[5:]))


def _valid_aware_timestamp(value):
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None


def main():
    # Fail closed before calling the connector, even if its configuration changes.
    required = {
        "AURORA_IBKR_MODE": "PAPER",
        "AURORA_IBKR_HOST": "127.0.0.1",
        "AURORA_IBKR_PORT": "4002",
    }
    invalid = [key for key, expected in required.items()
               if os.environ.get(key) != expected]
    if invalid or os.environ.get("AURORA_IBKR_ENABLED", "false").lower() != "true":
        print(json.dumps({"status": "BLOCKED", "reason": "PAPER_LOCAL_ONLY_CONFIGURATION_REQUIRED",
                          "order_submission_allowed": False}))
        return 2
    try:
        snapshot = get_ibkr_read_only_snapshot()
    except Exception:
        print(json.dumps({"status": "ERROR", "reason": "SNAPSHOT_PROBE_FAILED",
                          "order_submission_allowed": False}))
        return 1
    if not isinstance(snapshot, dict):
        print(json.dumps({"status": "ERROR", "reason": "INVALID_SNAPSHOT",
                          "order_submission_allowed": False}))
        return 1
    complete = snapshot.get("requests_complete")
    if not isinstance(complete, dict):
        complete = {}
    # Whitelist only non-sensitive diagnostic fields; never serialize raw snapshot.
    config = snapshot.get("config")
    if not isinstance(config, dict):
        config = {}
    account_guard = snapshot.get("paper_account_guard")
    if not isinstance(account_guard, dict):
        account_guard = {}

    fingerprints = account_guard.get("verified_account_fingerprints")
    fingerprint = None
    if (isinstance(fingerprints, list) and len(fingerprints) == 1
            and _valid_fingerprint(fingerprints[0])):
        fingerprint = fingerprints[0]
    timestamp = snapshot.get("timestamp")
    if not _valid_aware_timestamp(timestamp):
        timestamp = None

    report = {
        "status": snapshot.get("status") if snapshot.get("status") in ("CONNECTED", "BLOCKED", "DISABLED", "ERROR", "NOT_INSTALLED") else "UNKNOWN",
        "connection_status": snapshot.get("connection_status") if snapshot.get("connection_status") in ("CONNECTED", "NOT_ATTEMPTED", "FAILED", "DISCONNECTED") else "UNKNOWN",
        "paper_endpoint_safe": config.get("endpoint_safe") is True,
        "hard_blocked": snapshot.get("order_submission_hard_blocked") is True,
        "live_trading_allowed": False,
        "paper_account_verified": (
            account_guard.get("paper_account_verified") is True
            and fingerprint is not None
        ),
        "paper_account_fingerprint": fingerprint,
        "snapshot_generated_at_utc": timestamp,
        "requests_complete": {key: complete.get(key) is True for key in
                              ("managed_accounts", "account_summary", "positions", "open_orders", "executions")},
    }
    # Explicit negative evidence must never be overridden by a healthy snapshot.
    if snapshot.get("live_trading_allowed") is not False or config.get("read_only") is not True or config.get("mode") != "PAPER":
        report["paper_endpoint_safe"] = False
    print(json.dumps(report, sort_keys=True))
    return 0 if (report["status"] == "CONNECTED" and report["connection_status"] == "CONNECTED"
                 and report["paper_endpoint_safe"] and report["hard_blocked"]
                 and report["paper_account_verified"]
                 and report["paper_account_fingerprint"] is not None
                 and report["snapshot_generated_at_utc"] is not None
                 and all(report["requests_complete"].values())) else 1


if __name__ == "__main__":
    raise SystemExit(main())
