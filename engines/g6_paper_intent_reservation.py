"""Offline durable reservation for Paper intents. No broker API, no orders.

SQLite UNIQUE fingerprint + BEGIN IMMEDIATE prevent concurrent duplicate reservations.
A reservation is NOT an authorization to submit; broker reconciliation is required.
"""
import sqlite3
from pathlib import Path
from engines.g6_paper_intent_inspection import intent_fingerprint

def reserve_paper_intent(account, order, database_path):
    fingerprint = intent_fingerprint(account, order)
    path = Path(database_path)
    if not path.is_file():
        return {"status": "BLOCKED", "reason": "DATABASE_NOT_INITIALIZED",
                "broker_submission_allowed": False}
    try:
        with sqlite3.connect(str(path), timeout=5, isolation_level=None) as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "INSERT INTO paper_intents (fingerprint, state) VALUES (?, 'RESERVED')",
                (fingerprint,),
            )
            connection.commit()
    except sqlite3.IntegrityError:
        return {"status": "BLOCKED", "reason": "DUPLICATE_OR_UNSAFE_STATE",
                "broker_submission_allowed": False}
    except (sqlite3.Error, OSError):
        return {"status": "BLOCKED", "reason": "RESERVATION_FAILED",
                "broker_submission_allowed": False}
    return {"status": "RESERVED_OFFLINE", "fingerprint": fingerprint,
            "reason": "BROKER_RECONCILIATION_AND_APPROVAL_REQUIRED",
            "broker_submission_allowed": False}

def initialize_paper_intent_database(database_path):
    """Explicit operator setup; must not be called as automatic recovery."""
    with sqlite3.connect(str(database_path)) as connection:
        connection.execute(
            "CREATE TABLE IF NOT EXISTS paper_intents ("
            "fingerprint TEXT PRIMARY KEY NOT NULL, "
            "state TEXT NOT NULL CHECK(state IN ('RESERVED','RECONCILE_REQUIRED')))"
        )
