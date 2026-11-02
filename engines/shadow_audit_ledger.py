"""Persistent append-only idempotency ledger for G4 shadow orders."""

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import stat


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

    def _prepare_trusted_file(self):
        self.path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        if self.path.parent.is_symlink():
            raise RuntimeError(
                "SHADOW_LEDGER_PARENT_SYMLINK_FORBIDDEN"
            )

        nofollow = getattr(
            os,
            "O_NOFOLLOW",
            0,
        )
        if not nofollow:
            raise RuntimeError(
                "SHADOW_LEDGER_NOFOLLOW_UNAVAILABLE"
            )

        try:
            metadata = self.path.lstat()
        except FileNotFoundError:
            flags = (
                os.O_RDWR
                |
                os.O_CREAT
                |
                os.O_EXCL
                |
                nofollow
                |
                getattr(
                    os,
                    "O_CLOEXEC",
                    0,
                )
            )
            descriptor = os.open(
                self.path,
                flags,
                0o600,
            )
            try:
                os.fchmod(
                    descriptor,
                    0o600,
                )
                os.fsync(
                    descriptor
                )
            finally:
                os.close(
                    descriptor
                )
            metadata = self.path.lstat()

        trusted = (
            stat.S_ISREG(metadata.st_mode)
            and metadata.st_uid == os.geteuid()
            and stat.S_IMODE(metadata.st_mode) == 0o600
            and metadata.st_nlink == 1
        )
        if not trusted:
            raise RuntimeError(
                "SHADOW_LEDGER_FILE_UNTRUSTED"
            )

        return (
            metadata.st_dev,
            metadata.st_ino,
        )

    def _connect(self):
        expected_dev, expected_ino = (
            self._prepare_trusted_file()
        )

        connection = sqlite3.connect(
            str(self.path),
            timeout=10.0,
            isolation_level=None,
        )

        current = self.path.lstat()
        if (
            not stat.S_ISREG(current.st_mode)
            or current.st_dev != expected_dev
            or current.st_ino != expected_ino
            or current.st_uid != os.geteuid()
            or stat.S_IMODE(current.st_mode) != 0o600
            or current.st_nlink != 1
        ):
            connection.close()
            raise RuntimeError(
                "SHADOW_LEDGER_FILE_CHANGED_DURING_OPEN"
            )

        connection.execute("PRAGMA busy_timeout = 10000")
        connection.execute("PRAGMA synchronous = FULL")
        connection.execute(SCHEMA)
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
