"""Offline tests; never connect to a broker or submit orders."""
import unittest
from scripts.paper_readonly_acceptance_validator import evaluate_report


def valid_report():
    return {
        "status": "CONNECTED", "connection_status": "CONNECTED",
        "paper_endpoint_safe": True, "hard_blocked": True,
        "live_trading_allowed": False, "paper_account_verified": True,
        "paper_account_evidence_token": "IBKR-EVID-ABCDEF1234567890",
        "snapshot_generated_at_utc": "2026-11-01T12:00:00+00:00",
        "requests_complete": {k: True for k in
            ("managed_accounts", "account_summary", "positions", "open_orders", "executions")}
    }


class TestReadOnlyAcceptance(unittest.TestCase):
    def test_valid_diagnostic_still_never_authorizes_order(self):
        result = evaluate_report(valid_report())
        self.assertEqual(result["status"], "READ_ONLY_SNAPSHOT_VALIDATED")
        self.assertIs(result["paper_order_submission_allowed"], False)
        self.assertIs(result["live_trading_allowed"], False)
        self.assertIs(result["evidence_authenticity_verified"], False)
        self.assertIs(result["broker_session_independently_verified"], False)
        self.assertIs(result["release_approved"], False)
        self.assertIs(result["diagnostic_binding_fields_valid"], True)
        self.assertEqual(result["paper_account_evidence_token"],
                         "IBKR-EVID-ABCDEF1234567890")

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

    def test_invalid_evidence_token_fails_closed(self):
        for value in (None, "", "DU1234567", "IBKR-ABCDEF1234",
                      "IBKR-EVID-abcdef1234567890",
                      "IBKR-EVID-ABCDEF123456789",
                      "IBKR-EVID-ABCDEF12345678901"):
            with self.subTest(value=value):
                report = valid_report()
                report["paper_account_evidence_token"] = value
                self.assertEqual(
                    evaluate_report(report)["reason"], "INVALID_ACCOUNT_EVIDENCE_TOKEN")

    def test_invalid_timestamp_fails_closed(self):
        for value in (None, "", "not-a-time", "2026-11-01T12:00:00",
                      "2026-11-01T15:00:00+03:00"):
            with self.subTest(value=value):
                report = valid_report()
                report["snapshot_generated_at_utc"] = value
                self.assertEqual(
                    evaluate_report(report)["reason"], "INVALID_SNAPSHOT_TIMESTAMP")

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
