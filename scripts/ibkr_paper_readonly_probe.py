"""Operator-invoked IBKR Paper connectivity probe. No orders or secrets printed.

Run only on the IB Gateway host. Connector itself hard-blocks placeOrder.
"""
import json
import os
import sys
from pathlib import Path

# Allow direct execution from any working directory on the Gateway VPS.
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from engines.ibkr_gateway_connector import get_ibkr_read_only_snapshot


def main():
    # Fail closed before calling the connector, even if its configuration changes.
    required = {
        "AURORA_IBKR_MODE": "PAPER",
        "AURORA_IBKR_HOST": "127.0.0.1",
        "AURORA_IBKR_PORT": "4002",
    }
    invalid = [key for key, expected in required.items()
               if os.environ.get(key, expected) != expected]
    if invalid or os.environ.get("AURORA_IBKR_ENABLED", "false").lower() != "true":
        print(json.dumps({"status": "BLOCKED", "reason": "PAPER_LOCAL_ONLY_CONFIGURATION_REQUIRED",
                          "order_submission_allowed": False}))
        return 2
    snapshot = get_ibkr_read_only_snapshot()
    complete = snapshot.get("requests_complete") or {}
    # Whitelist only non-sensitive diagnostic fields; never serialize raw snapshot.
    report = {
        "status": snapshot.get("status"),
        "connection_status": snapshot.get("connection_status"),
        "paper_endpoint_safe": (snapshot.get("config") or {}).get("endpoint_safe") is True,
        "hard_blocked": snapshot.get("order_submission_hard_blocked") is True,
        "live_trading_allowed": False,
        "paper_account_verified": (snapshot.get("paper_account_guard") or {}).get("paper_account_verified") is True,
        "requests_complete": {key: complete.get(key) is True for key in
                              ("managed_accounts", "account_summary", "positions", "open_orders", "executions")},
    }
    print(json.dumps(report, sort_keys=True))
    return 0 if (report["status"] == "CONNECTED" and report["paper_endpoint_safe"]
                 and report["hard_blocked"] and report["paper_account_verified"]
                 and all(report["requests_complete"].values())) else 1


if __name__ == "__main__":
    raise SystemExit(main())
