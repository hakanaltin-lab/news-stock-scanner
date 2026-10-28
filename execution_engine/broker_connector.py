"""Deprecated AURORA legacy execution connector.

V8.9.5 safety policy:
- This module is retained only for backward compatibility.
- It never connects to a real broker.
- It never reports ORDER_SENT/SUBMITTED.
- LIVE mode is rejected.
- Production IBKR work must use engines.ibkr_gateway_connector.
"""

from datetime import datetime, timezone


DEPRECATED_LEGACY_CONNECTOR = True
LIVE_TRADING_ALLOWED = False


class BrokerConnector:
    def __init__(self):
        self.status = "DEPRECATED"
        self.environment = "PAPER"
        self.connected = False
        self.orders = {}

    def connect_broker(self, api_key, environment):
        requested = str(environment or "").strip().upper()

        if requested != "PAPER":
            self.connected = False
            return {
                "status": "BLOCKED",
                "reason": "LEGACY_CONNECTOR_LIVE_OR_INVALID_MODE_BLOCKED",
                "environment": requested or None,
            }

        if not api_key:
            self.connected = False
            return {
                "status": "CONNECTION_FAILED",
                "reason": "LEGACY_SIMULATION_REQUIRES_NONEMPTY_TEST_TOKEN",
            }

        self.connected = True
        self.environment = "PAPER"
        return {
            "status": "SIMULATION_ONLY",
            "environment": "PAPER",
            "deprecated": True,
            "real_broker_connection": False,
        }

    def validate_environment(self):
        return "PAPER_MODE" if self.environment == "PAPER" else "BLOCKED"

    def submit_order(self, symbol, quantity, order_type):
        return {
            "status": "BLOCKED",
            "reason": "LEGACY_CONNECTOR_ORDER_SUBMISSION_DISABLED",
            "symbol": symbol,
            "quantity": quantity,
            "order_type": order_type,
            "environment": self.environment,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
