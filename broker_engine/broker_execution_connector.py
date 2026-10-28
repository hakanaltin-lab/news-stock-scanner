"""Deprecated broker execution connector.

V8.9.5 safety policy:
- Retained only for backward compatibility.
- Does not create broker-ready executable orders.
- Does not submit to any broker.
- LIVE execution is unavailable.
"""

from datetime import datetime, timezone
import uuid


DEPRECATED_LEGACY_CONNECTOR = True
LIVE_EXECUTION_ALLOWED = False


class BrokerExecutionConnector:
    def __init__(self):
        self.status = "DEPRECATED"
        self.orders = {}

    def create_order_request(
        self,
        symbol,
        action,
        quantity,
        order_type,
        approval_status
    ):
        order_id = str(uuid.uuid4())

        record = {
            "order_id": order_id,
            "symbol": symbol,
            "action": action,
            "quantity": quantity,
            "order_type": order_type,
            "approval_status": approval_status,
            "status": "BLOCKED",
            "reason": "V8_9_5_LEGACY_EXECUTION_CONNECTOR_DISABLED",
            "live_execution_allowed": False,
            "paper_order_submission_allowed": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        self.orders[order_id] = record
        return record

    def update_order_status(self, order_id, status):
        if order_id not in self.orders:
            return None

        self.orders[order_id]["status"] = "BLOCKED"
        self.orders[order_id]["requested_status"] = status
        self.orders[order_id]["reason"] = (
            "V8_9_5_LEGACY_EXECUTION_CONNECTOR_DISABLED"
        )
        self.orders[order_id]["updated_at"] = (
            datetime.now(timezone.utc).isoformat()
        )
        return self.orders[order_id]

    def get_order(self, order_id):
        return self.orders.get(order_id)

    def generate_execution_report(self):
        return {
            "engine": "V8.9.5 Deprecated Broker Execution Connector",
            "status": "BLOCKED",
            "live_execution_allowed": False,
            "paper_order_submission_allowed": False,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "total_orders": len(self.orders),
            "orders": self.orders,
        }
