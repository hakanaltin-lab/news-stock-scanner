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

    def test_deleted_database_does_not_silently_recreate_in_active_session(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "paper.sqlite3"
            journal = PersistentPaperIntentJournal(path)
            self.assertTrue(journal.reserve("order-3")["allowed"])
            path.unlink()
            self.assertEqual(journal.reserve("order-4")["reason"], "JOURNAL_UNAVAILABLE")
            self.assertFalse(journal.list_unresolved()["valid"])
            self.assertFalse(path.exists())

    def test_restart_after_database_loss_is_blocked(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "paper.sqlite3"
            journal = PersistentPaperIntentJournal(path)
            self.assertTrue(journal.reserve("order-5")["allowed"])
            self.assertTrue(Path(str(path) + ".initialized").exists())
            path.unlink()
            with self.assertRaisesRegex(RuntimeError, "PAPER_JOURNAL_LOST"):
                PersistentPaperIntentJournal(path)
            self.assertFalse(path.exists())

    def test_existing_unregistered_database_requires_review(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "legacy.sqlite3"
            path.write_bytes(b"not a trusted database")
            with self.assertRaisesRegex(RuntimeError, "UNREGISTERED_PAPER_JOURNAL"):
                PersistentPaperIntentJournal(path)
            self.assertFalse(Path(str(path) + ".initialized").exists())

    def test_corrupted_registered_database_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "paper.sqlite3"
            PersistentPaperIntentJournal(path)
            path.write_bytes(b"corrupted sqlite database")
            with self.assertRaises(Exception):
                PersistentPaperIntentJournal(path)

    def test_memory_database_rejected(self):
        with self.assertRaises(ValueError):
            PersistentPaperIntentJournal(":memory:")


if __name__ == "__main__":
    unittest.main()
