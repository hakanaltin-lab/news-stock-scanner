"""Conservative in-process preflight for paper order intents.

Not a broker connector. No live order capability. In-memory duplicate
tracking is insufficient across process restarts; persistent broker-side
reconciliation is required before deployment.
"""
from datetime import datetime, timezone
import math

class PaperIntentGuard:
    def __init__(self):
        self._seen = set()

    def check(self, intent, *, broker_connected=False, account_type=None,
              run_mode=None, now=None):
        reasons = []
        if not isinstance(intent, dict):
            intent = {}
            reasons.append("INVALID_INTENT")
        if broker_connected is not True:
            reasons.append("BROKER_DISCONNECTED")
        if account_type != "PAPER":
            reasons.append("ACCOUNT_NOT_VERIFIED_PAPER")
        if run_mode != "PAPER_ENABLED":
            reasons.append("PAPER_MODE_NOT_ARMED")
        key = intent.get("client_order_id")
        if not isinstance(key, str) or not key.strip():
            reasons.append("MISSING_ORDER_ID")
        elif key in self._seen:
            reasons.append("DUPLICATE_ORDER_ID")
        symbol = intent.get("symbol")
        if not isinstance(symbol, str) or not symbol.strip():
            reasons.append("INVALID_SYMBOL")
        side = intent.get("side")
        if side not in ("BUY", "SELL"):
            reasons.append("INVALID_SIDE")
        qty = intent.get("quantity")
        if type(qty) not in (int, float) or not math.isfinite(qty) or qty <= 0:
            reasons.append("INVALID_QUANTITY")
        if reasons:
            return {"allowed": False, "reasons": reasons}
        # Reservation is atomic only within a single synchronous Python process.
        self._seen.add(key)
        return {"allowed": True, "reasons": []}

    def reset(self):
        # Resetting in-memory IDs is unsafe without broker reconciliation.
        raise RuntimeError("PERSISTENT_RECONCILIATION_REQUIRED")
