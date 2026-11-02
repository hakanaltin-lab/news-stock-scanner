"""Synthetic offline freshness tests. No IBKR connection or orders."""
import unittest
from datetime import datetime, timezone, timedelta
from scripts.paper_readonly_evidence_freshness import evaluate_freshness


class EvidenceFreshnessTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 2, 12, 0, tzinfo=timezone.utc)

    def check(self, seconds, expected):
        stamp = (self.now + timedelta(seconds=seconds)).isoformat()
        result = evaluate_freshness({"snapshot_generated_at_utc": stamp}, now=self.now)
        self.assertEqual(result["reason"], expected)
        self.assertFalse(result["paper_order_submission_allowed"])
        self.assertFalse(result["live_trading_allowed"])
        self.assertFalse(result["release_approved"])
        self.assertFalse(result["broker_session_independently_verified"])

    def test_recent_is_not_release_approval(self):
        self.check(-60, "FRESHNESS_ONLY_NOT_AUTHENTICITY_OR_RELEASE_APPROVAL")

    def test_old_report_rejected(self):
        self.check(-301, "STALE_TIMESTAMP")

    def test_future_report_rejected(self):
        self.check(31, "FUTURE_TIMESTAMP")

    def test_boundary_accepted_only_as_diagnostic(self):
        self.check(-300, "FRESHNESS_ONLY_NOT_AUTHENTICITY_OR_RELEASE_APPROVAL")

    def test_missing_and_naive_timestamps_rejected(self):
        self.assertEqual(evaluate_freshness({}, self.now)["status"], "BLOCKED")
        self.assertEqual(
            evaluate_freshness({"snapshot_generated_at_utc": "2026-11-02T12:00:00"}, self.now)["reason"],
            "NON_UTC_TIMESTAMP",
        )


if __name__ == "__main__":
    unittest.main()
