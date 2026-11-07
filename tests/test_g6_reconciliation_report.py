import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from engines.g6_paper_intent_journal import PersistentPaperIntentJournal
from engines.g6_ibkr_paper_snapshot_adapter import normalize_ibkr_paper_orders
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

    def test_adapter_to_journal_to_report_never_authorizes_orders(self):
        with tempfile.TemporaryDirectory() as folder:
            journal = PersistentPaperIntentJournal(Path(folder) / "paper.sqlite")
            self.assertTrue(journal.reserve("paper-1")["allowed"])
            self.assertTrue(journal.reserve("paper-2")["allowed"])
            self.assertTrue(journal.mark_unknown("paper-2"))
            snapshot = normalize_ibkr_paper_orders(
                [{"orderRef": "paper-1", "account": "DU123"}],
                account_id="DU123", captured_at=NOW,
                transport_authenticated=True, complete=True,
            )
            report = build_g6_reconciliation_report(
                journal, snapshot, expected_account_id="DU123", now=NOW
            )
            self.assertEqual(report["status"], "BLOCKED")
            self.assertEqual(report["reason"], "UNRESOLVED_LOCAL_ORDERS")
            self.assertEqual(report["matched_count"], 1)
            self.assertEqual(report["unresolved_order_ids"], ["paper-2"])
            self.assertFalse(report["execution_allowed"])
            self.assertFalse(report["paper_order_submission_allowed"])
            self.assertTrue(report["manual_review_required"])
            self.assertFalse(journal.reserve("paper-2")["allowed"])

    def test_stale_snapshot_blocks_end_to_end_without_changing_journal(self):
        with tempfile.TemporaryDirectory() as folder:
            journal = PersistentPaperIntentJournal(Path(folder) / "paper.sqlite")
            self.assertTrue(journal.reserve("paper-stale")["allowed"])
            snapshot = normalize_ibkr_paper_orders(
                [{"orderRef": "paper-stale", "account": "DU123"}],
                account_id="DU123",
                captured_at=datetime(2026, 11, 7, 11, 58, tzinfo=timezone.utc),
                transport_authenticated=True, complete=True,
            )
            before = journal.list_unresolved()
            report = build_g6_reconciliation_report(
                journal, snapshot, expected_account_id="DU123", now=NOW
            )
            self.assertEqual(report["status"], "BLOCKED")
            self.assertEqual(report["reason"], "STALE_OR_INVALID_SNAPSHOT")
            self.assertFalse(report["paper_order_submission_allowed"])
            self.assertTrue(report["manual_review_required"])
            self.assertEqual(journal.list_unresolved(), before)

    def test_mismatched_paper_account_blocks_without_changing_journal(self):
        with tempfile.TemporaryDirectory() as folder:
            journal = PersistentPaperIntentJournal(Path(folder) / "paper.sqlite")
            self.assertTrue(journal.reserve("paper-account")["allowed"])
            snapshot = normalize_ibkr_paper_orders(
                [{"orderRef": "paper-account", "account": "DU999"}],
                account_id="DU999", captured_at=NOW,
                transport_authenticated=True, complete=True,
            )
            before = journal.list_unresolved()
            report = build_g6_reconciliation_report(
                journal, snapshot, expected_account_id="DU123", now=NOW
            )
            self.assertEqual(report["status"], "BLOCKED")
            self.assertEqual(report["reason"], "BROKER_ACCOUNT_MISMATCH")
            self.assertEqual(report["matched_count"], 0)
            self.assertFalse(report["paper_order_submission_allowed"])
            self.assertEqual(journal.list_unresolved(), before)

    def test_incomplete_broker_snapshot_blocks_without_changing_journal(self):
        with tempfile.TemporaryDirectory() as folder:
            journal = PersistentPaperIntentJournal(Path(folder) / "paper.sqlite")
            self.assertTrue(journal.reserve("paper-partial")["allowed"])
            snapshot = normalize_ibkr_paper_orders(
                [{"orderRef": "paper-partial", "account": "DU123"}],
                account_id="DU123", captured_at=NOW,
                transport_authenticated=True, complete=False,
            )
            before = journal.list_unresolved()
            report = build_g6_reconciliation_report(
                journal, snapshot, expected_account_id="DU123", now=NOW
            )
            self.assertEqual(report["status"], "BLOCKED")
            self.assertEqual(report["reason"], "INCOMPLETE_OR_UNVERIFIED_SNAPSHOT")
            self.assertFalse(report["execution_allowed"])
            self.assertFalse(report["paper_order_submission_allowed"])
            self.assertTrue(report["manual_review_required"])
            self.assertEqual(journal.list_unresolved(), before)

    def test_unauthenticated_broker_snapshot_blocks_without_changing_journal(self):
        with tempfile.TemporaryDirectory() as folder:
            journal = PersistentPaperIntentJournal(Path(folder) / "paper.sqlite")
            self.assertTrue(journal.reserve("paper-unverified")["allowed"])
            snapshot = normalize_ibkr_paper_orders(
                [{"orderRef": "paper-unverified", "account": "DU123"}],
                account_id="DU123", captured_at=NOW,
                transport_authenticated=False, complete=True,
            )
            before = journal.list_unresolved()
            report = build_g6_reconciliation_report(
                journal, snapshot, expected_account_id="DU123", now=NOW
            )
            self.assertEqual(report["status"], "BLOCKED")
            self.assertEqual(report["reason"], "INCOMPLETE_OR_UNVERIFIED_SNAPSHOT")
            self.assertFalse(report["paper_order_submission_allowed"])
            self.assertTrue(report["manual_review_required"])
            self.assertEqual(journal.list_unresolved(), before)

    def test_malformed_broker_payload_blocks_and_preserves_journal(self):
        with tempfile.TemporaryDirectory() as folder:
            journal = PersistentPaperIntentJournal(Path(folder) / "paper.sqlite")
            self.assertTrue(journal.reserve("paper-malformed")["allowed"])
            before = journal.list_unresolved()
            for malformed in (None, {"orders": []}, ["not-an-order"]):
                with self.subTest(malformed=repr(malformed)):
                    snapshot = normalize_ibkr_paper_orders(
                        malformed, account_id="DU123", captured_at=NOW,
                        transport_authenticated=True, complete=True,
                    )
                    report = build_g6_reconciliation_report(
                        journal, snapshot, expected_account_id="DU123", now=NOW
                    )
                    self.assertEqual(report["status"], "BLOCKED")
                    self.assertEqual(report["reason"], "UNVERIFIED_PAPER_ACCOUNT")
                    self.assertFalse(report["execution_allowed"])
                    self.assertFalse(report["paper_order_submission_allowed"])
                    self.assertEqual(journal.list_unresolved(), before)

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
