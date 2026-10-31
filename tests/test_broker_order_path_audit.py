"""Regression checks: legacy broker connectors must never submit orders.

These tests are intentionally network-free and safe in CI.
"""
import unittest

from engines.broker_connector import BrokerConnector as LegacyEngine
from execution_engine.broker_connector import BrokerConnector as LegacyExecution
from broker_engine.broker_execution_connector import BrokerExecutionConnector


class LegacyOrderPathSafetyTests(unittest.TestCase):
    def test_engine_submit_is_blocked(self):
        connector = LegacyEngine()
        self.assertEqual(connector.connect()["status"], "BLOCKED")
        for payload in ({"symbol": "NVDA", "quantity": 1}, {}):
            self.assertEqual(connector.submit_order(payload)["status"], "BLOCKED")

    def test_execution_submit_is_blocked_in_all_modes(self):
        connector = LegacyExecution()
        for mode in ("PAPER", "LIVE", "", "invalid"):
            connector.connect_broker("test-only", mode)
            result = connector.submit_order("NVDA", 1, "LIMIT")
            self.assertEqual(result["status"], "BLOCKED")
            self.assertNotIn(result["status"], {"ORDER_SENT", "SUBMITTED"})

    def test_broker_execution_never_promotes_order(self):
        connector = BrokerExecutionConnector()
        order = connector.create_order_request("NVDA", "BUY", 1, "LIMIT", "APPROVED")
        self.assertEqual(order["status"], "BLOCKED")
        for status in ("SUBMITTED", "FILLED", "ORDER_SENT"):
            updated = connector.update_order_status(order["order_id"], status)
            self.assertEqual(updated["status"], "BLOCKED")
        report = connector.generate_execution_report()
        self.assertFalse(report["live_execution_allowed"])
        self.assertFalse(report["paper_order_submission_allowed"])


if __name__ == "__main__":
    unittest.main()
