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
        if sentinel.exists() and sentinel.read_text(encoding="utf-8") != "AURORA_PAPER_JOURNAL_V1\n":
            raise RuntimeError("PAPER_JOURNAL_SENTINEL_INVALID")
        if path.is_file() and not sentinel.exists():
            # An unregistered existing database must be reviewed/migrated
            # separately; never silently trust it or overwrite its history.
            raise RuntimeError("UNREGISTERED_PAPER_JOURNAL")
        with sqlite3.connect(self.database_path, timeout=5) as db:
            if db.execute("PRAGMA quick_check").fetchone() != ("ok",):
                raise RuntimeError("PAPER_JOURNAL_INTEGRITY_FAILURE")
            if sentinel.exists():
                schema = db.execute(
                    "SELECT sql FROM sqlite_master WHERE type='table' AND name='paper_intents'"
                ).fetchone()
                required = ("client_order_id", "status", "created_at")
                if not schema or not all(name in schema[0] for name in required):
                    raise RuntimeError("PAPER_JOURNAL_SCHEMA_MISSING")
                columns = {
                    row[1]: row for row in db.execute("PRAGMA table_info(paper_intents)").fetchall()
                }
                if not all(name in columns for name in required):
                    raise RuntimeError("PAPER_JOURNAL_SCHEMA_MISSING")
                normalized_schema = " ".join(schema[0].upper().split())
                if (columns["client_order_id"][5] != 1
                        or columns["client_order_id"][3] != 1
                        or columns["status"][3] != 1
                        or "CHECK(STATUSIN('RESERVED','UNKNOWN','RECONCILED'))" not in normalized_schema.replace(" ", "")):
                    raise RuntimeError("PAPER_JOURNAL_SCHEMA_INVALID")
            db.execute("""CREATE TABLE IF NOT EXISTS paper_intents (
                client_order_id TEXT PRIMARY KEY NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('RESERVED', 'UNKNOWN', 'RECONCILED')),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )""")
        # Detect database file replacement during the current process lifetime.
        self._database_identity = (path.stat().st_dev, path.stat().st_ino)
        if not sentinel.exists():
            try:
                with sentinel.open("x", encoding="utf-8") as marker:
                    marker.write("AURORA_PAPER_JOURNAL_V1\n")
            except FileExistsError:
                pass

    def _connect(self):
        path = Path(self.database_path)
        try:
            current_identity = (path.stat().st_dev, path.stat().st_ino)
            if current_identity != self._database_identity:
                raise sqlite3.OperationalError("PAPER_JOURNAL_FILE_REPLACED")
        except OSError as exc:
            raise sqlite3.OperationalError("PAPER_JOURNAL_FILE_UNAVAILABLE") from exc
        # mode=rw prevents silently recreating an erased journal on restart.
        uri = "file:" + quote(str(Path(self.database_path).resolve()), safe="/") + "?mode=rw"
        sentinel = Path(self.database_path + ".initialized")
        if not sentinel.is_file():
            raise sqlite3.OperationalError("PAPER_JOURNAL_SENTINEL_MISSING")
        try:
            if sentinel.read_text(encoding="utf-8") != "AURORA_PAPER_JOURNAL_V1\n":
                raise sqlite3.OperationalError("PAPER_JOURNAL_SENTINEL_INVALID")
        except OSError as exc:
            raise sqlite3.OperationalError("PAPER_JOURNAL_SENTINEL_UNAVAILABLE") from exc
        db = sqlite3.connect(uri, timeout=5, uri=True)
        try:
            if db.execute("PRAGMA quick_check").fetchone() != ("ok",):
                raise sqlite3.DatabaseError("PAPER_JOURNAL_INTEGRITY_FAILURE")
            return db
        except BaseException:
            db.close()
            raise

    def reserve(self, client_order_id):
        if (not isinstance(client_order_id, str) or not client_order_id.strip()
                or client_order_id != client_order_id.strip() or len(client_order_id) > 128):
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
