"""G6.22 composition tests: valid synthetic reports never become trading approval."""
import unittest
from datetime import datetime, timezone
from scripts.paper_readonly_acceptance_validator import evaluate_report
from scripts.paper_readonly_evidence_freshness import evaluate_freshness


class EvidenceCompositionTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 2, 12, 0, tzinfo=timezone.utc)
        self.report = {
            "status": "CONNECTED",
            "connection_status": "CONNECTED",
            "paper_endpoint_safe": True,
            "hard_blocked": True,
            "live_trading_allowed": False,
            "paper_account_verified": True,
            "paper_account_evidence_token": "IBKR-EVID-" + "A" * 16,
            "snapshot_generated_at_utc": "2026-11-02T12:00:00Z",
            "requests_complete": {
                "managed_accounts": True, "account_summary": True,
                "positions": True, "open_orders": True, "executions": True,
            },
        }

    def test_two_diagnostic_passes_still_deny_all_orders(self):
        binding = evaluate_report(self.report)
        freshness = evaluate_freshness(self.report, now=self.now)
        self.assertEqual(binding["status"], "READ_ONLY_SNAPSHOT_VALIDATED")
        self.assertEqual(freshness["status"], "FRESHNESS_DIAGNOSTIC_PASSED")
        for result in (binding, freshness):
            self.assertFalse(result["release_approved"])
            self.assertFalse(result["paper_order_submission_allowed"])
            self.assertFalse(result["live_trading_allowed"])
            self.assertFalse(result["broker_session_independently_verified"])

    def test_valid_binding_but_stale_snapshot_blocks_freshness(self):
        self.report["snapshot_generated_at_utc"] = "2026-11-02T11:54:59Z"
        self.assertEqual(evaluate_report(self.report)["status"], "READ_ONLY_SNAPSHOT_VALIDATED")
        result = evaluate_freshness(self.report, now=self.now)
        self.assertEqual(result["reason"], "STALE_TIMESTAMP")
        self.assertFalse(result["release_approved"])


if __name__ == "__main__":
    unittest.main()
