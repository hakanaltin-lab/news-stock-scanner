"""G6.21 offline regression checks: diagnostic JSON must never authorize orders.

These tests use synthetic reports only; no broker imports, network or credentials.
"""
import unittest

from scripts.paper_readonly_acceptance_validator import evaluate_report


def synthetic_report():
    return {
        "status": "CONNECTED",
        "connection_status": "CONNECTED",
        "paper_endpoint_safe": True,
        "hard_blocked": True,
        "live_trading_allowed": False,
        "paper_account_verified": True,
        "paper_account_evidence_token": "IBKR-EVID-" + "A" * 16,
        "snapshot_generated_at_utc": "2026-11-02T00:00:00+00:00",
        "requests_complete": {
            "managed_accounts": True,
            "account_summary": True,
            "positions": True,
            "open_orders": True,
            "executions": True,
        },
    }


class ReadOnlyEvidenceBoundaryTests(unittest.TestCase):
    def test_synthetic_success_is_diagnostic_only(self):
        result = evaluate_report(synthetic_report())
        self.assertEqual(result["status"], "READ_ONLY_SNAPSHOT_VALIDATED")
        self.assertFalse(result["release_approved"])
        self.assertFalse(result["evidence_authenticity_verified"])
        self.assertFalse(result["broker_session_independently_verified"])
        self.assertFalse(result["paper_order_submission_allowed"])
        self.assertFalse(result["live_trading_allowed"])

    def test_incomplete_callback_fails_closed(self):
        report = synthetic_report()
        report["requests_complete"]["executions"] = False
        result = evaluate_report(report)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertFalse(result["release_approved"])

    def test_missing_identity_fails_closed(self):
        report = synthetic_report()
        report["paper_account_verified"] = False
        result = evaluate_report(report)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertFalse(result["paper_order_submission_allowed"])

    def test_live_flag_fails_closed(self):
        report = synthetic_report()
        report["live_trading_allowed"] = True
        result = evaluate_report(report)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertFalse(result["live_trading_allowed"])


if __name__ == "__main__":
    unittest.main()
