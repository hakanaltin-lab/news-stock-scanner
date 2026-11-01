"""G6.14 atomic authorization reservation ledger.

This module persistently reserves a validated G6.13 contract at most once.
It has no broker dependency, creates no broker order object, and never grants
Paper or Live submission permission.
"""

from datetime import datetime, timezone
import hashlib
import hmac
import json
import os
from pathlib import Path
import sqlite3
from uuid import UUID

from engines.paper_submission_contract import CONTRACT_VERSION


LEDGER_VERSION = "AURORA_G6_14_AUTHORIZATION_RESERVATION_LEDGER_V1"
DEFAULT_MAX_CONTRACT_AGE_SECONDS = 30

SCHEMA = """
CREATE TABLE IF NOT EXISTS paper_authorization_reservations (
    authorization_id TEXT PRIMARY KEY,
    idempotency_key TEXT NOT NULL UNIQUE,
    shadow_order_sha256 TEXT NOT NULL UNIQUE,
    intent_sha256 TEXT NOT NULL,
    contract_sha256 TEXT NOT NULL UNIQUE,
    contract_version TEXT NOT NULL,
    contract_generated_at TEXT NOT NULL,
    reservation_state TEXT NOT NULL
        CHECK (reservation_state = 'RESERVED_NON_EXECUTABLE'),
    reserved_at TEXT NOT NULL,
    reservation_receipt_sha256 TEXT NOT NULL UNIQUE
)
"""


def _digest(payload):
    encoded = json.dumps(
        payload or {},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _valid_sha256(value):
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(c in "0123456789abcdef" for c in value)
    )


def _utc_datetime(value):
    if isinstance(value, datetime):
        parsed = value
    else:
        text = str(value or "").strip()
        if not text:
            return None
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def _uuid4(value):
    text = str(value or "").strip()
    try:
        parsed = UUID(text)
    except (ValueError, AttributeError):
        return None
    return text if parsed.version == 4 and str(parsed) == text else None


def _valid_idempotency_key(value):
    return (
        isinstance(value, str)
        and 8 <= len(value) <= 128
        and value.isascii()
        and all(c.isalnum() or c in "-_" for c in value)
    )


def _safe_flags(contract):
    return all(
        contract.get(name) is False
        for name in (
            "broker_submission_allowed",
            "paper_order_submission_allowed",
            "live_execution_allowed",
            "automatic_promotion_allowed",
            "real_money_trading_allowed",
            "broker_order_object_allowed",
        )
    )


def _contract_payload(contract):
    return {
        "version": contract.get("version"),
        "generated_at": contract.get("generated_at"),
        "authorization_id": contract.get("authorization_id"),
        "intent_sha256": contract.get("intent_sha256"),
        "shadow_order_sha256": contract.get("shadow_order_sha256"),
        "idempotency_key": contract.get("idempotency_key"),
    }


def _base(status="BLOCKED", reason="RESERVATION_NOT_ALLOWED"):
    return {
        "engine": "AURORA G6.14 Authorization Reservation Ledger",
        "ledger_version": LEDGER_VERSION,
        "status": status,
        "reason": reason,
        "reserved": False,
        "broker_submission_allowed": False,
        "paper_order_submission_allowed": False,
        "live_execution_allowed": False,
        "automatic_promotion_allowed": False,
        "real_money_trading_allowed": False,
        "broker_order_object_allowed": False,
    }


def validate_reservable_contract(
    contract,
    now=None,
    max_contract_age_seconds=DEFAULT_MAX_CONTRACT_AGE_SECONDS,
):
    result = _base()
    if not isinstance(contract, dict):
        return {**result, "reason": "INVALID_CONTRACT"}

    generated_at = _utc_datetime(contract.get("generated_at"))
    current = _utc_datetime(now) or datetime.now(timezone.utc)
    age = None
    if generated_at is not None:
        age = (current - generated_at).total_seconds()

    authorization_id = _uuid4(contract.get("authorization_id"))
    idempotency_key = contract.get("idempotency_key")
    intent_sha256 = contract.get("intent_sha256")
    shadow_sha256 = contract.get("shadow_order_sha256")
    contract_sha256 = contract.get("contract_sha256")

    checks = {
        "contract_status_valid": (
            contract.get("status")
            == "SUBMISSION_CONTRACT_VALIDATED_NON_EXECUTABLE"
            and contract.get("reason")
            == "ARTIFACTS_BOUND_BUT_BROKER_PERMISSION_NOT_GRANTED"
            and contract.get("next_gate")
            == "PAPER_BROKER_ADAPTER_CODE_REVIEW_REQUIRED"
            and contract.get(
                "authorization_id_must_be_atomically_consumed_before_submission"
            ) is True
        ),
        "contract_version_valid": contract.get("version") == CONTRACT_VERSION,
        "submission_flags_safe": _safe_flags(contract),
        "authorization_id_uuid4": authorization_id is not None,
        "idempotency_key_valid": _valid_idempotency_key(idempotency_key),
        "intent_digest_valid": _valid_sha256(intent_sha256),
        "shadow_digest_valid": _valid_sha256(shadow_sha256),
        "contract_digest_valid": _valid_sha256(contract_sha256),
        "contract_time_valid": (
            age is not None
            and age >= -2
            and age <= float(max_contract_age_seconds)
        ),
    }

    expected_contract_sha256 = _digest(_contract_payload(contract))
    checks["contract_digest_self_consistent"] = (
        _valid_sha256(contract_sha256)
        and hmac.compare_digest(contract_sha256, expected_contract_sha256)
    )

    failures = [name for name, passed in checks.items() if not passed]
    if failures:
        return {
            **result,
            "reason": "CONTRACT_NOT_RESERVABLE",
            "checks": checks,
            "contract_age_seconds": age,
        }

    return {
        **result,
        "status": "RESERVABLE_NON_EXECUTABLE",
        "reason": "CONTRACT_INTEGRITY_VALIDATED",
        "checks": checks,
        "authorization_id": authorization_id,
        "idempotency_key": idempotency_key,
        "intent_sha256": intent_sha256,
        "shadow_order_sha256": shadow_sha256,
        "contract_sha256": contract_sha256,
        "contract_generated_at": generated_at.isoformat(),
        "contract_age_seconds": age,
    }


class PaperAuthorizationReservationLedger:
    """Append-only at-most-once reservation ledger for validated contracts."""

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

    def reserve(
        self,
        contract,
        now=None,
        max_contract_age_seconds=DEFAULT_MAX_CONTRACT_AGE_SECONDS,
    ):
        current = _utc_datetime(now) or datetime.now(timezone.utc)
        validated = validate_reservable_contract(
            contract,
            now=current,
            max_contract_age_seconds=max_contract_age_seconds,
        )
        if validated.get("status") != "RESERVABLE_NON_EXECUTABLE":
            return validated

        authorization_id = validated["authorization_id"]
        idempotency_key = validated["idempotency_key"]
        shadow_sha256 = validated["shadow_order_sha256"]
        intent_sha256 = validated["intent_sha256"]
        contract_sha256 = validated["contract_sha256"]
        contract_generated_at = validated["contract_generated_at"]
        reserved_at = current.isoformat()

        receipt_payload = {
            "ledger_version": LEDGER_VERSION,
            "authorization_id": authorization_id,
            "idempotency_key": idempotency_key,
            "shadow_order_sha256": shadow_sha256,
            "intent_sha256": intent_sha256,
            "contract_sha256": contract_sha256,
            "contract_version": CONTRACT_VERSION,
            "contract_generated_at": contract_generated_at,
            "reservation_state": "RESERVED_NON_EXECUTABLE",
            "reserved_at": reserved_at,
        }
        receipt_sha256 = _digest(receipt_payload)

        try:
            connection = self._connect()
        except (OSError, sqlite3.Error):
            return {
                **_base("BLOCKED", "LEDGER_UNAVAILABLE"),
                "authorization_id": authorization_id,
                "idempotency_key": idempotency_key,
            }

        try:
            connection.execute("BEGIN IMMEDIATE")
            try:
                connection.execute(
                    """
                    INSERT INTO paper_authorization_reservations (
                        authorization_id,
                        idempotency_key,
                        shadow_order_sha256,
                        intent_sha256,
                        contract_sha256,
                        contract_version,
                        contract_generated_at,
                        reservation_state,
                        reserved_at,
                        reservation_receipt_sha256
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        authorization_id,
                        idempotency_key,
                        shadow_sha256,
                        intent_sha256,
                        contract_sha256,
                        CONTRACT_VERSION,
                        contract_generated_at,
                        "RESERVED_NON_EXECUTABLE",
                        reserved_at,
                        receipt_sha256,
                    ),
                )
                connection.execute("COMMIT")
            except sqlite3.IntegrityError:
                connection.execute("ROLLBACK")
                existing = connection.execute(
                    """
                    SELECT
                        authorization_id,
                        idempotency_key,
                        shadow_order_sha256,
                        contract_sha256,
                        reservation_state,
                        reserved_at,
                        reservation_receipt_sha256
                    FROM paper_authorization_reservations
                    WHERE authorization_id = ?
                       OR idempotency_key = ?
                       OR shadow_order_sha256 = ?
                       OR contract_sha256 = ?
                    LIMIT 1
                    """,
                    (
                        authorization_id,
                        idempotency_key,
                        shadow_sha256,
                        contract_sha256,
                    ),
                ).fetchone()
                return {
                    **_base("BLOCKED", "AUTHORIZATION_OR_ORDER_ALREADY_RESERVED"),
                    "duplicate": True,
                    "authorization_id": authorization_id,
                    "idempotency_key": idempotency_key,
                    "existing_authorization_id": existing[0] if existing else None,
                    "existing_idempotency_key": existing[1] if existing else None,
                    "existing_shadow_order_sha256": existing[2] if existing else None,
                    "existing_contract_sha256": existing[3] if existing else None,
                    "existing_reservation_state": existing[4] if existing else None,
                    "existing_reserved_at": existing[5] if existing else None,
                    "existing_reservation_receipt_sha256": (
                        existing[6] if existing else None
                    ),
                }
            except sqlite3.Error:
                try:
                    connection.execute("ROLLBACK")
                except sqlite3.Error:
                    pass
                return {
                    **_base("BLOCKED", "LEDGER_UNAVAILABLE"),
                    "authorization_id": authorization_id,
                    "idempotency_key": idempotency_key,
                }
        finally:
            connection.close()

        return {
            **_base(
                "AUTHORIZATION_RESERVED_NON_EXECUTABLE",
                "AT_MOST_ONCE_RESERVATION_RECORDED",
            ),
            "reserved": True,
            "duplicate": False,
            "authorization_id": authorization_id,
            "idempotency_key": idempotency_key,
            "contract_sha256": contract_sha256,
            "reservation_state": "RESERVED_NON_EXECUTABLE",
            "reserved_at": reserved_at,
            "reservation_receipt_sha256": receipt_sha256,
            "next_gate": "PAPER_BROKER_ADAPTER_REVIEW_AND_FAILURE_SEMANTICS_REQUIRED",
        }
