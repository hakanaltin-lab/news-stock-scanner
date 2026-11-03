"""Regression checks: deprecated broker adapters must never submit orders.

Run: python -m unittest discover -s tests -p 'test_legacy_broker_fail_closed.py'
"""
import unittest

from execution_engine.broker_connector import BrokerConnector
from broker_engine.broker_execution_connector import BrokerExecutionConnector


class LegacyBrokerFailClosedTests(unittest.TestCase):
    def test_legacy_connection_never_claims_real_broker(self):
        connector = BrokerConnector()
        response = connector.connect_broker("dummy-test-token", "PAPER")
        self.assertEqual(response["status"], "SIMULATION_ONLY")
        self.assertIs(response["real_broker_connection"], False)

    def test_legacy_live_connection_blocked(self):
        connector = BrokerConnector()
        response = connector.connect_broker("dummy-test-token", "LIVE")
        self.assertEqual(response["status"], "BLOCKED")
        self.assertFalse(connector.connected)

    def test_legacy_submit_always_blocked(self):
        connector = BrokerConnector()
        connector.connect_broker("dummy-test-token", "PAPER")
        response = connector.submit_order("AAPL", 1, "MKT")
        self.assertEqual(response["status"], "BLOCKED")

    def test_deprecated_execution_request_never_sent(self):
        connector = BrokerExecutionConnector()
        record = connector.create_order_request("AAPL", "BUY", 1, "MKT", "APPROVED")
        self.assertEqual(record["status"], "BLOCKED")
        self.assertIs(record["paper_order_submission_allowed"], False)
        self.assertIs(record["live_execution_allowed"], False)
        updated = connector.update_order_status(record["order_id"], "FILLED")
        self.assertEqual(updated["status"], "BLOCKED")
        report = connector.generate_execution_report()
        self.assertIs(report["live_execution_allowed"], False)


if __name__ == "__main__":
    unittest.main()
