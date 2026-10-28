"""Deprecated broker connector foundation.

V8.9.5 keeps this module fail-closed for backward compatibility only.
Production broker integration must use engines.ibkr_gateway_connector.
"""

from datetime import datetime, timezone


DEPRECATED_LEGACY_CONNECTOR = True
LIVE_TRADING = False


class BrokerConnector:
    def __init__(self, broker="LEGACY"):
        self.broker = broker
        self.connected = False

    def connect(self):
        self.connected = False
        return {
            "status": "BLOCKED",
            "reason": "DEPRECATED_LEGACY_CONNECTOR",
            "broker": self.broker,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def get_account_status(self):
        return {
            "broker": self.broker,
            "mode": "PAPER",
            "status": "BLOCKED",
            "buying_power": None,
            "portfolio_value": None,
        }

    def submit_order(self, order):
        return {
            "status": "BLOCKED",
            "reason": "DEPRECATED_LEGACY_CONNECTOR",
            "order": order,
        }

    def get_positions(self):
        return {
            "positions": [],
            "status": "BLOCKED",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


def broker_health_check():
    connector = BrokerConnector()
    return {
        "engine": "V8.9.5 Deprecated Broker Connector",
        "connection": connector.connect(),
        "account": connector.get_account_status(),
    }
