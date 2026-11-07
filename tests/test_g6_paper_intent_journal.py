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
            for value in (None, [], {}, "", " ", " order-1", "order-1 ", "x" * 129):
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

    def test_missing_sentinel_blocks_active_session(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "paper.sqlite3"
            journal = PersistentPaperIntentJournal(path)
            Path(str(path) + ".initialized").unlink()
            self.assertEqual(journal.reserve("new-order")["reason"], "JOURNAL_UNAVAILABLE")
            self.assertFalse(journal.list_unresolved()["valid"])

    def test_tampered_sentinel_blocks_restart_and_active_session(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "paper.sqlite3"
            journal = PersistentPaperIntentJournal(path)
            Path(str(path) + ".initialized").write_text("INVALID", encoding="utf-8")
            self.assertEqual(journal.reserve("new-order")["reason"], "JOURNAL_UNAVAILABLE")
            with self.assertRaisesRegex(RuntimeError, "PAPER_JOURNAL_SENTINEL_INVALID"):
                PersistentPaperIntentJournal(path)

    def test_invalid_utf8_sentinel_fails_closed_in_active_session(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "paper.sqlite3"
            journal = PersistentPaperIntentJournal(path)
            Path(str(path) + ".initialized").write_bytes(b"\\xff\\xfe")
            self.assertEqual(journal.reserve("new-order")["reason"], "JOURNAL_UNAVAILABLE")
            self.assertFalse(journal.mark_unknown("new-order"))
            self.assertEqual(journal.list_unresolved()["valid"], False)

    def test_database_replacement_blocks_active_session(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "paper.sqlite3"
            journal = PersistentPaperIntentJournal(path)
            self.assertTrue(journal.reserve("order-1")["allowed"])
            replacement = Path(directory) / "replacement.sqlite3"
            replacement.write_bytes(path.read_bytes())
            replacement.replace(path)
            self.assertEqual(journal.reserve("order-2")["reason"], "JOURNAL_UNAVAILABLE")
            self.assertFalse(journal.list_unresolved()["valid"])

    def test_sentinel_content_survives_restart_and_allows_reservations(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "paper.sqlite3"
            first = PersistentPaperIntentJournal(path)
            self.assertEqual(
                Path(str(path) + ".initialized").read_text(encoding="utf-8"),
                "AURORA_PAPER_JOURNAL_V1\n",
            )
            self.assertTrue(first.reserve("order-first")["allowed"])
            second = PersistentPaperIntentJournal(path)
            self.assertTrue(second.reserve("order-second")["allowed"])
            self.assertEqual(len(second.list_unresolved()["orders"]), 2)

    def test_registered_empty_database_does_not_regenerate_missing_schema(self):
        import sqlite3
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "paper.sqlite3"
            PersistentPaperIntentJournal(path)
            path.unlink()
            with sqlite3.connect(path):
                pass
            with self.assertRaisesRegex(RuntimeError, "PAPER_JOURNAL_SCHEMA_MISSING"):
                PersistentPaperIntentJournal(path)

    def test_registered_schema_without_unique_primary_key_is_rejected(self):
        import sqlite3
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "paper.sqlite3"
            PersistentPaperIntentJournal(path)
            with sqlite3.connect(path) as db:
                db.execute("DROP TABLE paper_intents")
                db.execute(
                    "CREATE TABLE paper_intents (client_order_id TEXT, status TEXT NOT NULL, created_at TEXT)"
                )
            with self.assertRaisesRegex(RuntimeError, "PAPER_JOURNAL_SCHEMA_INVALID"):
                PersistentPaperIntentJournal(path)

    def test_registered_schema_without_status_check_is_rejected(self):
        import sqlite3
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "paper.sqlite3"
            PersistentPaperIntentJournal(path)
            with sqlite3.connect(path) as db:
                db.execute("DROP TABLE paper_intents")
                db.execute(
                    "CREATE TABLE paper_intents (client_order_id TEXT PRIMARY KEY NOT NULL, "
                    "status TEXT NOT NULL, created_at TEXT NOT NULL)"
                )
            with self.assertRaisesRegex(RuntimeError, "PAPER_JOURNAL_SCHEMA_INVALID"):
                PersistentPaperIntentJournal(path)

    def test_memory_database_rejected(self):
        with self.assertRaises(ValueError):
            PersistentPaperIntentJournal(":memory:")


if __name__ == "__main__":
    unittest.main()
