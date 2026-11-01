"""Offline tests; never connect to a broker or submit orders."""
import unittest
from scripts.paper_readonly_acceptance_validator import evaluate_report

def valid_report():
    return {
        "status": "CONNECTED", "connection_status": "CONNECTED",
        "paper_endpoint_safe": True, "hard_blocked": True,
        "live_trading_allowed": False, "paper_account_verified": True,
        "requests_complete": {k: True for k in
            ("managed_accounts", "account_summary", "positions", "open_orders", "executions")}
    }

class TestReadOnlyAcceptance(unittest.TestCase):
    def test_valid_diagnostic_still_never_authorizes_order(self):
        result = evaluate_report(valid_report())
        self.assertEqual(result["status"], "READ_ONLY_SNAPSHOT_VALIDATED")
        self.assertIs(result["paper_order_submission_allowed"], False)
        self.assertIs(result["live_trading_allowed"], False)

    def test_invalid_reports_fail_closed(self):
        for report in (None, [], {}, True, "CONNECTED"):
            with self.subTest(report=repr(report)):
                self.assertEqual(evaluate_report(report)["status"], "BLOCKED")

    def test_missing_or_false_guards_fail_closed(self):
        for key in ("paper_endpoint_safe", "hard_blocked", "live_trading_allowed",
                    "paper_account_verified"):
            for value in (None, True, False):
                report = valid_report()
                report[key] = value
                if key == "live_trading_allowed" and value is False:
                    continue
                if key != "live_trading_allowed" and value is True:
                    continue
                with self.subTest(key=key, value=value):
                    self.assertEqual(evaluate_report(report)["status"], "BLOCKED")

    def test_missing_broker_callback_fails_closed(self):
        for key in valid_report()["requests_complete"]:
            report = valid_report()
            report["requests_complete"].pop(key)
            with self.subTest(key=key):
                self.assertEqual(evaluate_report(report)["reason"], "INCOMPLETE_REQUESTS")

    def test_missing_connection_fails_closed(self):
        report = valid_report()
        report["connection_status"] = "DISCONNECTED"
        self.assertEqual(evaluate_report(report)["reason"], "BROKER_NOT_CONNECTED")

if __name__ == "__main__":
    unittest.main()
