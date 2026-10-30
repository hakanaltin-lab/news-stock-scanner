"""Read-only integrity verification for the persistent G4 shadow ledger."""

import hashlib
import hmac
import json
from datetime import datetime, timezone
from pathlib import Path
import sqlite3


REQUIRED_COLUMNS = {
    "idempotency_key",
    "shadow_order_id",
    "symbol",
    "payload_sha256",
    "payload_json",
    "recorded_at",
}

RECEIPT_BINDING_FIELDS = (
    "idempotency_key",
    "shadow_order_id",
    "symbol",
    "payload_sha256",
    "recorded_at",
)


def _is_sha256(value):
    text = str(value or "")
    return len(text) == 64 and all(
        character in "0123456789abcdef"
        for character in text.lower()
    )


def receipt_binding_sha256(receipt):
    """Return a canonical digest for one accepted ledger receipt."""
    receipt = receipt or {}
    if (
        receipt.get("recorded") is not True
        or receipt.get("duplicate") is not False
        or not all(
            isinstance(receipt.get(name), str)
            and receipt.get(name)
            for name in RECEIPT_BINDING_FIELDS
        )
        or not _is_sha256(receipt.get("payload_sha256"))
    ):
        return None
    canonical = {
        "duplicate": False,
        "recorded": True,
        **{
            name: receipt[name]
            for name in RECEIPT_BINDING_FIELDS
        },
    }
    encoded = json.dumps(
        canonical,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _blocked(reason, **extra):
    return {
        "engine": "AURORA V8.9.24 Shadow Ledger Integrity Verifier",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "BLOCKED",
        "failure_reasons": [reason],
        "broker_submission_allowed": False,
        "paper_order_submission_allowed": False,
        "live_execution_allowed": False,
        "automatic_promotion_allowed": False,
        **extra,
    }


def verify_shadow_ledger(path, expected_receipt=None):
    expected_receipt_sha256 = receipt_binding_sha256(expected_receipt)
    if expected_receipt_sha256 is None:
        return _blocked("EXPECTED_LEDGER_RECEIPT_REQUIRED")

    target = Path(path)
    if not target.is_file():
        return _blocked("LEDGER_NOT_FOUND")

    connection = None
    try:
        connection = sqlite3.connect(
            f"file:{target.resolve().as_posix()}?mode=ro",
            uri=True,
            timeout=10.0,
        )
        integrity_rows = connection.execute(
            "PRAGMA integrity_check"
        ).fetchall()
        integrity_ok = integrity_rows == [("ok",)]

        columns = {
            row[1]
            for row in connection.execute(
                "PRAGMA table_info(shadow_order_receipts)"
            ).fetchall()
        }
        if not REQUIRED_COLUMNS.issubset(columns):
            return _blocked("LEDGER_SCHEMA_INVALID")

        rows = connection.execute(
            """
            SELECT
                idempotency_key,
                shadow_order_id,
                symbol,
                payload_sha256,
                payload_json,
                recorded_at
            FROM shadow_order_receipts
            ORDER BY recorded_at, idempotency_key
            """
        ).fetchall()
    except (OSError, sqlite3.Error):
        return _blocked("LEDGER_READ_FAILED")
    finally:
        if connection is not None:
            connection.close()

    failures = []
    if not integrity_ok:
        failures.append("SQLITE_INTEGRITY_CHECK_FAILED")

    seen_keys = set()
    latest_recorded_at = None
    expected_receipt_bound = False
    for index, row in enumerate(rows, start=1):
        (
            idempotency_key,
            shadow_order_id,
            symbol,
            payload_sha256,
            payload_json,
            recorded_at,
        ) = row
        prefix = f"ROW_{index}"

        row_receipt_sha256 = receipt_binding_sha256(
            {
                "recorded": True,
                "duplicate": False,
                "idempotency_key": idempotency_key,
                "shadow_order_id": shadow_order_id,
                "symbol": symbol,
                "payload_sha256": payload_sha256,
                "recorded_at": recorded_at,
            }
        )
        if (
            row_receipt_sha256 is not None
            and hmac.compare_digest(
                row_receipt_sha256,
                expected_receipt_sha256,
            )
        ):
            expected_receipt_bound = True

        if idempotency_key in seen_keys:
            failures.append(f"{prefix}_DUPLICATE_IDEMPOTENCY_KEY")
        seen_keys.add(idempotency_key)

        calculated = hashlib.sha256(
            str(payload_json).encode("utf-8")
        ).hexdigest()
        if calculated != payload_sha256:
            failures.append(f"{prefix}_PAYLOAD_HASH_MISMATCH")

        try:
            payload = json.loads(payload_json)
        except (TypeError, json.JSONDecodeError):
            failures.append(f"{prefix}_PAYLOAD_JSON_INVALID")
            continue

        order = payload.get("shadow_order") or {}
        evidence = payload.get("evidence") or {}
        if (
            order.get("idempotency_key") != idempotency_key
            or order.get("shadow_order_id") != shadow_order_id
            or order.get("symbol") != symbol
        ):
            failures.append(f"{prefix}_RECEIPT_FIELDS_MISMATCH")

        if order.get("status") != "SHADOW_ACCEPTED":
            failures.append(f"{prefix}_SHADOW_STATUS_INVALID")

        if not all(
            order.get(name) is False
            for name in (
                "broker_submission_allowed",
                "paper_order_submission_allowed",
                "live_execution_allowed",
            )
        ):
            failures.append(f"{prefix}_SUBMISSION_FLAGS_NOT_SAFE")

        if not all(
            _is_sha256(evidence.get(name))
            for name in (
                "readiness_proof_sha256",
                "market_data_proof_sha256",
            )
        ):
            failures.append(f"{prefix}_EVIDENCE_DIGEST_INVALID")

        latest_recorded_at = max(
            latest_recorded_at or str(recorded_at),
            str(recorded_at),
        )

    if not expected_receipt_bound:
        failures.append("EXPECTED_LEDGER_RECEIPT_NOT_FOUND")

    failures = sorted(set(failures))
    return {
        "engine": "AURORA V8.9.24 Shadow Ledger Integrity Verifier",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "LEDGER_VERIFIED" if not failures else "BLOCKED",
        "record_count": len(rows),
        "latest_recorded_at": latest_recorded_at,
        "expected_receipt_sha256": expected_receipt_sha256,
        "expected_receipt_bound": expected_receipt_bound,
        "failure_reasons": failures,
        "broker_submission_allowed": False,
        "paper_order_submission_allowed": False,
        "live_execution_allowed": False,
        "automatic_promotion_allowed": False,
    }
