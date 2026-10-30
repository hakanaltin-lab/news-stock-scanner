"""Persistent append-only idempotency ledger for G4 shadow orders."""

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sqlite3


SCHEMA = """
CREATE TABLE IF NOT EXISTS shadow_order_receipts (
    idempotency_key TEXT PRIMARY KEY,
    shadow_order_id TEXT NOT NULL,
    symbol TEXT NOT NULL,
    payload_sha256 TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    recorded_at TEXT NOT NULL
)
"""


class ShadowAuditLedger:
    """Record accepted shadows once, without update or delete operations."""

    def __init__(self, path):
        self.path = Path(path)

    def _connect(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(
            str(self.path),
            timeout=10.0,
            isolation_level=None,
        )
        connection.execute("PRAGMA busy_timeout = 10000")
        connection.execute("PRAGMA synchronous = FULL")
        connection.execute(SCHEMA)
        os.chmod(self.path, 0o600)
        return connection

    @staticmethod
    def _canonical(payload):
        return json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
        )

    def record_shadow_order(self, shadow_order, evidence):
        shadow_order = shadow_order or {}
        evidence = evidence or {}
        idempotency_key = str(
            shadow_order.get("idempotency_key") or ""
        ).strip()
        shadow_order_id = str(
            shadow_order.get("shadow_order_id") or ""
        ).strip()
        symbol = str(shadow_order.get("symbol") or "").strip().upper()

        if not idempotency_key or not shadow_order_id or not symbol:
            raise ValueError("INCOMPLETE_SHADOW_LEDGER_RECORD")

        recorded_at = datetime.now(timezone.utc).isoformat()
        payload = {
            "shadow_order": shadow_order,
            "evidence": evidence,
            "recorded_at": recorded_at,
        }
        payload_json = self._canonical(payload)
        payload_sha256 = hashlib.sha256(
            payload_json.encode("utf-8")
        ).hexdigest()

        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            try:
                connection.execute(
                    """
                    INSERT INTO shadow_order_receipts (
                        idempotency_key,
                        shadow_order_id,
                        symbol,
                        payload_sha256,
                        payload_json,
                        recorded_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        idempotency_key,
                        shadow_order_id,
                        symbol,
                        payload_sha256,
                        payload_json,
                        recorded_at,
                    ),
                )
                connection.execute("COMMIT")
            except sqlite3.IntegrityError:
                connection.execute("ROLLBACK")
                existing = connection.execute(
                    """
                    SELECT shadow_order_id, symbol, payload_sha256, recorded_at
                    FROM shadow_order_receipts
                    WHERE idempotency_key = ?
                    """,
                    (idempotency_key,),
                ).fetchone()
                return {
                    "recorded": False,
                    "duplicate": True,
                    "idempotency_key": idempotency_key,
                    "existing_shadow_order_id": existing[0] if existing else None,
                    "symbol": existing[1] if existing else symbol,
                    "payload_sha256": existing[2] if existing else None,
                    "recorded_at": existing[3] if existing else None,
                }
        finally:
            connection.close()

        return {
            "recorded": True,
            "duplicate": False,
            "idempotency_key": idempotency_key,
            "shadow_order_id": shadow_order_id,
            "symbol": symbol,
            "payload_sha256": payload_sha256,
            "recorded_at": recorded_at,
        }
