import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from engines.g6_paper_intent_journal import PersistentPaperIntentJournal
from engines.g6_reconciliation_report import build_g6_reconciliation_report

NOW = datetime(2026, 11, 7, 12, 0, tzinfo=timezone.utc)


class ReconciliationReportTests(unittest.TestCase):
    def test_clean_snapshot_still_requires_manual_review(self):
        with tempfile.TemporaryDirectory() as folder:
            journal = PersistentPaperIntentJournal(Path(folder) / "paper.sqlite")
            journal.reserve("order-1")
            snapshot = {
                "account_type": "PAPER", "account_id": "DU123",
                "verified": True, "complete": True,
                "timestamp": NOW.isoformat(),
                "orders": [{"client_order_id": "order-1"}],
            }
            report = build_g6_reconciliation_report(
                journal, snapshot, expected_account_id="DU123", now=NOW
            )
            self.assertEqual(report["status"], "REVIEW_REQUIRED")
            self.assertEqual(report["matched_count"], 1)
            self.assertFalse(report["execution_allowed"])
            self.assertFalse(report["paper_order_submission_allowed"])
            self.assertTrue(report["manual_review_required"])

    def test_invalid_review_timestamp_fails_closed(self):
        for invalid in ("2026-11-07", datetime(2026, 11, 7, 12, 0)):
            with self.subTest(invalid=str(invalid)):
                report = build_g6_reconciliation_report(
                    None, None, expected_account_id="DU123", now=invalid
                )
                self.assertEqual(report["status"], "BLOCKED")
                self.assertEqual(report["reason"], "INVALID_REVIEW_TIMESTAMP")
                self.assertFalse(report["paper_order_submission_allowed"])
                self.assertTrue(report["manual_review_required"])

    def test_missing_snapshot_is_blocked(self):
        report = build_g6_reconciliation_report(
            None, None, expected_account_id="DU123", now=NOW
        )
        self.assertEqual(report["status"], "BLOCKED")
        self.assertFalse(report["live_execution_allowed"])

if __name__ == "__main__":
    unittest.main()
