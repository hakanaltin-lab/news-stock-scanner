import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from engines.g6_paper_intent_journal import PersistentPaperIntentJournal
from engines.g6_paper_reconciliation_runner import reconcile_journal

NOW = datetime(2026, 11, 7, 12, 0, tzinfo=timezone.utc)

class JournalReconciliationTests(unittest.TestCase):
    def test_unresolved_journal_reconciles_read_only(self):
        with tempfile.TemporaryDirectory() as folder:
            journal = PersistentPaperIntentJournal(Path(folder) / "paper.db")
            journal.reserve("paper-1")
            journal.reserve("paper-2")
            journal.mark_unknown("paper-2")
            snapshot = {
                "account_type": "PAPER", "account_id": "DU123",
                "verified": True, "complete": True, "timestamp": NOW.isoformat(),
                "orders": [{"client_order_id": "paper-1"}],
            }
            result = reconcile_journal(journal, snapshot, expected_account_id="DU123", now=NOW)
            self.assertFalse(result["ready"])
            self.assertEqual(result["matched"], ["paper-1"])
            self.assertEqual(result["unresolved"], ["paper-2"])

    def test_account_id_is_mandatory(self):
        result = reconcile_journal(None, {}, expected_account_id=None, now=NOW)
        self.assertEqual(result["reason"], "EXPECTED_PAPER_ACCOUNT_REQUIRED")

    def test_broken_journal_blocks(self):
        result = reconcile_journal(None, {}, expected_account_id="DU123", now=NOW)
        self.assertEqual(result["reason"], "JOURNAL_UNAVAILABLE")

if __name__ == "__main__":
    unittest.main()
