import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch
from engines.g6_paper_intent_journal import PersistentPaperIntentJournal


class JournalTests(unittest.TestCase):
    def test_duplicate_survives_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "paper.sqlite3"
            first = PersistentPaperIntentJournal(path)
            self.assertTrue(first.reserve("order-1")["allowed"])
            second = PersistentPaperIntentJournal(path)
            self.assertEqual(second.reserve("order-1")["reason"], "DUPLICATE_OR_UNRECONCILED")

    def test_concurrent_duplicate_reservations_allow_exactly_one(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "paper.sqlite3"
            journals = [PersistentPaperIntentJournal(path) for _ in range(8)]
            with ThreadPoolExecutor(max_workers=8) as pool:
                results = list(pool.map(lambda journal: journal.reserve("same-order"), journals))
            self.assertEqual(sum(result["allowed"] for result in results), 1)
            self.assertTrue(all(
                result["reason"] in ("RESERVED", "DUPLICATE_OR_UNRECONCILED")
                for result in results
            ))
            self.assertEqual(len(journals[0].list_unresolved()["orders"]), 1)

    def test_concurrent_distinct_reservations_are_all_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "paper.sqlite3"
            journal = PersistentPaperIntentJournal(path)
            order_ids = [f"order-{index}" for index in range(8)]
            with ThreadPoolExecutor(max_workers=8) as pool:
                results = list(pool.map(journal.reserve, order_ids))
            self.assertTrue(all(result["allowed"] for result in results))
            inventory = journal.list_unresolved()
            self.assertTrue(inventory["valid"])
            self.assertEqual(
                {item["client_order_id"] for item in inventory["orders"]}, set(order_ids)
            )

    def test_unknown_cannot_be_reused(self):
        with tempfile.TemporaryDirectory() as directory:
            journal = PersistentPaperIntentJournal(Path(directory) / "paper.sqlite3")
            self.assertTrue(journal.reserve("order-2")["allowed"])
            self.assertTrue(journal.mark_unknown("order-2"))
            self.assertFalse(journal.reserve("order-2")["allowed"])

    def test_concurrent_unknown_transition_only_succeeds_once(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "paper.sqlite3"
            journal = PersistentPaperIntentJournal(path)
            self.assertTrue(journal.reserve("uncertain-order")["allowed"])
            with ThreadPoolExecutor(max_workers=8) as pool:
                results = list(pool.map(journal.mark_unknown, ["uncertain-order"] * 8))
            self.assertEqual(sum(results), 1)
            self.assertEqual(journal.list_unresolved()["orders"], [
                {"client_order_id": "uncertain-order", "status": "UNKNOWN"}
            ])
            self.assertFalse(journal.reserve("uncertain-order")["allowed"])

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

    def test_invalid_utf8_sentinel_blocks_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "paper.sqlite3"
            PersistentPaperIntentJournal(path)
            Path(str(path) + ".initialized").write_bytes(bytes([255, 254]))
            with self.assertRaisesRegex(RuntimeError, "PAPER_JOURNAL_SENTINEL_INVALID"):
                PersistentPaperIntentJournal(path)

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

    def test_concurrent_sentinel_creation_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "paper.sqlite3"
            original_open = Path.open

            def competing_open(target, mode="r", *args, **kwargs):
                if str(target) == str(path) + ".initialized" and mode == "x":
                    raise FileExistsError("competing journal initializer")
                return original_open(target, mode, *args, **kwargs)

            with patch.object(Path, "open", competing_open):
                with self.assertRaisesRegex(RuntimeError, "PAPER_JOURNAL_INITIALIZATION_RACE"):
                    PersistentPaperIntentJournal(path)

    def test_memory_database_rejected(self):
        with self.assertRaises(ValueError):
            PersistentPaperIntentJournal(":memory:")


if __name__ == "__main__":
    unittest.main()
