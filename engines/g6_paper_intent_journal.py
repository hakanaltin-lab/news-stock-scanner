"""Persistent paper intent reservation; never submits broker orders.

SQLite UNIQUE key prevents duplicate reservations across restarts/processes.
UNKNOWN is intentionally not auto-retryable; broker reconciliation is required.
"""
import sqlite3
from urllib.parse import quote
from pathlib import Path


class PersistentPaperIntentJournal:
    def __init__(self, database_path):
        self.database_path = str(database_path)
        if self.database_path == ":memory:":
            raise ValueError("PERSISTENT_DATABASE_REQUIRED")
        path = Path(self.database_path)
        if not path.parent.exists():
            raise ValueError("DATABASE_DIRECTORY_MISSING")
        # Sidecar sentinel detects a lost database on process restart.
        # The sentinel must reside on durable storage, independently backed up.
        sentinel = Path(str(path) + ".initialized")
        if sentinel.exists() and not path.is_file():
            raise RuntimeError("PAPER_JOURNAL_LOST")
        if path.is_file() and not sentinel.exists():
            # Existing legacy databases are accepted, but deployment must
            # independently verify their provenance before use.
            pass
        with sqlite3.connect(self.database_path, timeout=5) as db:
            db.execute("""CREATE TABLE IF NOT EXISTS paper_intents (
                client_order_id TEXT PRIMARY KEY NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('RESERVED', 'UNKNOWN', 'RECONCILED')),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )""")
        if not sentinel.exists():
            try:
                with sentinel.open("x", encoding="utf-8") as marker:
                    marker.write("AURORA_PAPER_JOURNAL_V1\\n")
            except FileExistsError:
                pass

    def _connect(self):
        # mode=rw prevents silently recreating an erased journal on restart.
        uri = "file:" + quote(str(Path(self.database_path).resolve()), safe="/") + "?mode=rw"
        return sqlite3.connect(uri, timeout=5, uri=True)

    def reserve(self, client_order_id):
        if not isinstance(client_order_id, str) or not client_order_id.strip() or len(client_order_id) > 128:
            return {"allowed": False, "reason": "INVALID_ORDER_ID"}
        try:
            with self._connect() as db:
                db.execute(
                    "INSERT INTO paper_intents (client_order_id, status) VALUES (?, 'RESERVED')",
                    (client_order_id,),
                )
            return {"allowed": True, "reason": "RESERVED"}
        except sqlite3.IntegrityError:
            return {"allowed": False, "reason": "DUPLICATE_OR_UNRECONCILED"}
        except sqlite3.Error:
            return {"allowed": False, "reason": "JOURNAL_UNAVAILABLE"}

    def mark_unknown(self, client_order_id):
        """After uncertain broker outcome, block retry until external reconciliation."""
        try:
            with self._connect() as db:
                cursor = db.execute(
                    "UPDATE paper_intents SET status='UNKNOWN' WHERE client_order_id=? AND status='RESERVED'",
                    (client_order_id,),
                )
                return cursor.rowcount == 1
        except sqlite3.Error:
            return False

    def list_unresolved(self):
        """Read-only inventory for broker reconciliation; fail closed on DB errors."""
        try:
            with self._connect() as db:
                rows = db.execute(
                    "SELECT client_order_id, status FROM paper_intents "
                    "WHERE status IN ('RESERVED', 'UNKNOWN') ORDER BY client_order_id"
                ).fetchall()
            return {"valid": True, "orders": [
                {"client_order_id": key, "status": status} for key, status in rows
            ]}
        except sqlite3.Error:
            return {"valid": False, "orders": [], "reason": "JOURNAL_UNAVAILABLE"}
