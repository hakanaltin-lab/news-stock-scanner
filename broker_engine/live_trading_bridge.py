"""Deprecated live trading bridge.

V8.9.5 deliberately removes LIVE execution from the supported state machine.
This compatibility class always fails closed.
"""

from datetime import datetime, timezone
import uuid


LIVE_EXECUTION_ALLOWED = False


class LiveTradingBridge:
    def __init__(self):
        self.status = "DISABLED"
        self.execution_requests = {}

    def create_execution_request(
        self,
        symbol,
        action,
        quantity,
        approval_status,
        risk_status
    ):
        request_id = str(uuid.uuid4())
        request = {
            "request_id": request_id,
            "symbol": symbol,
            "action": action,
            "quantity": quantity,
            "approval_status": approval_status,
            "risk_status": risk_status,
            "status": "BLOCKED",
            "reason": "LIVE_TRADING_REMOVED_IN_V8_9_5",
            "live_execution_allowed": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self.execution_requests[request_id] = request
        return request

    def confirm_execution(self, request_id, broker_response):
        if request_id not in self.execution_requests:
            return None

        request = self.execution_requests[request_id]
        request["status"] = "BLOCKED"
        request["reason"] = "LIVE_TRADING_REMOVED_IN_V8_9_5"
        request["broker_response_recorded"] = bool(broker_response)
        request["live_execution_allowed"] = False
        request["updated_at"] = datetime.now(timezone.utc).isoformat()
        return request

    def cancel_execution(self, request_id, reason):
        if request_id not in self.execution_requests:
            return None

        request = self.execution_requests[request_id]
        request["status"] = "CANCELLED"
        request["reason"] = reason
        request["live_execution_allowed"] = False
        return request

    def get_execution_status(self, request_id):
        return self.execution_requests.get(request_id)

    def generate_execution_report(self):
        return {
            "engine": "V8.9.5 Disabled Live Trading Bridge",
            "status": "DISABLED",
            "live_execution_allowed": False,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "total_requests": len(self.execution_requests),
            "requests": self.execution_requests,
        }
