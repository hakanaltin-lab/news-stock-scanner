"""AURORA V8.9.5 shadow-only order management compatibility layer.

This module cannot produce executable broker orders. It may create a shadow
order only while AURORA_RUN_MODE=DRY_RUN.
"""

from datetime import datetime, timezone
import uuid

from engines.aurora_run_mode_engine import load_run_mode


class OrderManagementSystem:
    def __init__(self):
        self.status = "SHADOW_ONLY"
        self.orders = {}

    def create_trade_order(
        self,
        symbol,
        action,
        quantity,
        entry_price,
        stop_loss_percent,
        take_profit_percent
    ):
        run_mode = load_run_mode()

        if run_mode.get("mode") != "DRY_RUN":
            return {
                "status": "BLOCKED",
                "reason": "DRY_RUN_MODE_REQUIRED",
                "live_execution_allowed": False,
                "paper_order_submission_allowed": False,
            }

        order_id = str(uuid.uuid4())
        entry = float(entry_price)

        order = {
            "order_id": order_id,
            "symbol": symbol,
            "action": action,
            "quantity": quantity,
            "entry_price": entry,
            "stop_loss": entry * (1 - float(stop_loss_percent) / 100),
            "take_profit": entry * (1 + float(take_profit_percent) / 100),
            "status": "SHADOW_ONLY",
            "live_execution_allowed": False,
            "paper_order_submission_allowed": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        self.orders[order_id] = order
        return order

    def update_order_status(self, order_id, status):
        if order_id not in self.orders:
            return None

        order = self.orders[order_id]
        order["requested_status"] = status
        order["status"] = "SHADOW_ONLY"
        order["updated_at"] = datetime.now(timezone.utc).isoformat()
        return order

    def close_order(self, order_id, exit_price):
        if order_id not in self.orders:
            return None

        order = self.orders[order_id]
        order["exit_price"] = exit_price
        order["status"] = "SHADOW_CLOSED"
        order["closed_at"] = datetime.now(timezone.utc).isoformat()
        return order

    def get_active_orders(self):
        return [
            order
            for order in self.orders.values()
            if order.get("status") == "SHADOW_ONLY"
        ]

    def generate_order_report(self):
        return {
            "engine": "V8.9.5 Shadow Order Management System",
            "status": "SHADOW_ONLY",
            "live_execution_allowed": False,
            "paper_order_submission_allowed": False,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "total_orders": len(self.orders),
            "orders": self.orders,
        }
