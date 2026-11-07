import tempfile
import unittest
from pathlib import Path
from engines.g6_paper_intent_journal import PersistentPaperIntentJournal


class JournalTests(unittest.TestCase):
    def test_duplicate_survives_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "paper.sqlite3"
            first = PersistentPaperIntentJournal(path)
            self.assertTrue(first.reserve("order-1")["allowed"])
            second = PersistentPaperIntentJournal(path)
            self.assertEqual(second.reserve("order-1")["reason"], "DUPLICATE_OR_UNRECONCILED")

    def test_unknown_cannot_be_reused(self):
        with tempfile.TemporaryDirectory() as directory:
            journal = PersistentPaperIntentJournal(Path(directory) / "paper.sqlite3")
            self.assertTrue(journal.reserve("order-2")["allowed"])
            self.assertTrue(journal.mark_unknown("order-2"))
            self.assertFalse(journal.reserve("order-2")["allowed"])

    def test_malformed_id_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            journal = PersistentPaperIntentJournal(Path(directory) / "paper.sqlite3")
            for value in (None, [], {}, "", "x" * 129):
                with self.subTest(value=value):
                    self.assertFalse(journal.reserve(value)["allowed"])

    def test_memory_database_rejected(self):
        with self.assertRaises(ValueError):
            PersistentPaperIntentJournal(":memory:")


if __name__ == "__main__":
    unittest.main()
