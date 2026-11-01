"""G6.18 broker-neutral Paper adapter review envelope.

Builds a short-lived, review-only order envelope from the persisted G6.17
PREPARED attempt. No broker API, order object, submission, cancellation,
modification, or retry capability is present.
"""

from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import sqlite3
from uuid import UUID

from engines.paper_submission_attempt_journal import JOURNAL_VERSION


ENVELOPE_VERSION = "AURORA_G6_18_ADAPTER_REVIEW_ENVELOPE_V1"
DEFAULT_MAX_PREPARED_AGE_SECONDS = 30


def _digest(payload):
    try:
        encoded = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError, OverflowError):
        return None
    return hashlib.sha256(encoded).hexdigest()


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


def _valid_sha256(value):
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(c in "0123456789abcdef" for c in value)
    )


def _valid_token(value):
    return (
        isinstance(value, str)
        and value.startswith("IBKR-EVID-")
        and len(value) == 26
        and all(c in "0123456789ABCDEF" for c in value[10:])
    )


def _valid_symbol(value):
    return (
        isinstance(value, str)
        and value.isascii()
        and 1 <= len(value) <= 10
        and all(c.isupper() or c.isdigit() or c in ".-" for c in value)
    )


def _safe_base(status="BLOCKED", reason="ADAPTER_REVIEW_ENVELOPE_BLOCKED"):
    return {
        "engine": "AURORA G6.18 Paper Adapter Review Envelope",
        "envelope_version": ENVELOPE_VERSION,
        "status": status,
        "reason": reason,
        "review_only": True,
        "broker_submission_allowed": False,
        "paper_order_submission_allowed": False,
        "live_execution_allowed": False,
        "automatic_retry_allowed": False,
        "automatic_cancel_allowed": False,
        "automatic_modify_allowed": False,
        "broker_order_object_allowed": False,
        "broker_request_materialization_allowed": False,
    }


class PaperAdapterReviewEnvelopeBuilder:
    """Read-only verifier over the G6.17 attempt journal."""

    def __init__(self, attempt_journal_path):
        self.attempt_journal_path = Path(attempt_journal_path)

    def _connect_read_only(self):
        if not self.attempt_journal_path.exists():
            return None
        try:
            return sqlite3.connect(
                f"file:{self.attempt_journal_path}?mode=ro",
                uri=True,
                timeout=5.0,
            )
        except sqlite3.Error:
            return None

    @staticmethod
    def _event_digest(
        attempt_id,
        event_type,
        client_id,
        order_id,
        evidence_sha256,
        event_time,
    ):
        return _digest({
            "attempt_id": attempt_id,
            "event_type": event_type,
            "client_id": client_id,
            "order_id": order_id,
            "evidence_sha256": evidence_sha256,
            "event_time": event_time,
        })

    def build(
        self,
        attempt_id,
        now=None,
        max_prepared_age_seconds=DEFAULT_MAX_PREPARED_AGE_SECONDS,
    ):
        current = _utc_datetime(now)
        if now is not None and current is None:
            return {**_safe_base(), "reason": "INVALID_EVALUATION_TIME"}
        current = current or datetime.now(timezone.utc)

        canonical_attempt_id = _uuid4(attempt_id)
        if canonical_attempt_id is None:
            return {**_safe_base(), "reason": "INVALID_ATTEMPT_ID"}

        connection = self._connect_read_only()
        if connection is None:
            return {**_safe_base(), "reason": "ATTEMPT_JOURNAL_UNAVAILABLE"}

        try:
            try:
                registry = connection.execute(
                    """
                    SELECT
                        attempt_id,
                        authorization_id,
                        idempotency_key,
                        contract_sha256,
                        reservation_receipt_sha256,
                        intent_sha256,
                        expected_order_json,
                        expected_order_sha256,
                        paper_account_evidence_token,
                        prepared_at
                    FROM submission_attempt_registry
                    WHERE attempt_id = ?
                    """,
                    (canonical_attempt_id,),
                ).fetchone()
                latest = connection.execute(
                    """
                    SELECT
                        event_id,
                        attempt_id,
                        event_type,
                        client_id,
                        order_id,
                        evidence_sha256,
                        event_time,
                        event_sha256
                    FROM submission_attempt_events
                    WHERE attempt_id = ?
                    ORDER BY event_id DESC
                    LIMIT 1
                    """,
                    (canonical_attempt_id,),
                ).fetchone()
            except sqlite3.Error:
                return {**_safe_base(), "reason": "ATTEMPT_JOURNAL_SCHEMA_INVALID"}
        finally:
            connection.close()

        if registry is None or latest is None:
            return {**_safe_base(), "reason": "ATTEMPT_NOT_FOUND"}

        (
            stored_attempt_id,
            authorization_id,
            idempotency_key,
            contract_sha256,
            reservation_receipt_sha256,
            intent_sha256,
            expected_order_json,
            expected_order_sha256,
            account_token,
            prepared_at_text,
        ) = registry

        (
            _event_id,
            event_attempt_id,
            event_type,
            client_id,
            order_id,
            evidence_sha256,
            event_time,
            event_sha256,
        ) = latest

        if (
            stored_attempt_id != canonical_attempt_id
            or event_attempt_id != canonical_attempt_id
            or event_type != "PREPARED_NON_EXECUTABLE"
            or client_id is not None
            or order_id is not None
            or evidence_sha256 is not None
        ):
            return {
                **_safe_base(),
                "reason": "ATTEMPT_NOT_IN_PREPARED_REVIEW_STATE",
                "latest_event_type": event_type,
            }

        if (
            _uuid4(authorization_id) is None
            or not isinstance(idempotency_key, str)
            or not idempotency_key.strip()
            or not _valid_sha256(contract_sha256)
            or not _valid_sha256(reservation_receipt_sha256)
            or not _valid_sha256(intent_sha256)
            or not _valid_sha256(expected_order_sha256)
            or not _valid_sha256(event_sha256)
            or not _valid_token(account_token)
        ):
            return {**_safe_base(), "reason": "ATTEMPT_REGISTRY_IDENTITY_INVALID"}

        prepared_at = _utc_datetime(prepared_at_text)
        event_at = _utc_datetime(event_time)
        if prepared_at is None or event_at is None or event_at != prepared_at:
            return {**_safe_base(), "reason": "PREPARE_EVENT_TIME_MISMATCH"}

        age = (current - prepared_at).total_seconds()
        if age < 0 or age > float(max_prepared_age_seconds):
            return {
                **_safe_base(),
                "reason": "PREPARED_ATTEMPT_STALE",
                "prepared_age_seconds": age,
            }

        try:
            expected_order = json.loads(expected_order_json)
        except (TypeError, json.JSONDecodeError):
            return {**_safe_base(), "reason": "EXPECTED_ORDER_JSON_INVALID"}

        if (
            not isinstance(expected_order, dict)
            or set(expected_order) != {
                "symbol",
                "side",
                "quantity",
                "limit_price",
            }
            or not _valid_symbol(expected_order.get("symbol"))
            or expected_order.get("side") not in ("BUY", "SELL")
            or type(expected_order.get("quantity")) is not int
            or expected_order.get("quantity") <= 0
            or type(expected_order.get("limit_price")) not in (int, float)
            or not math.isfinite(expected_order.get("limit_price"))
            or expected_order.get("limit_price") <= 0
        ):
            return {**_safe_base(), "reason": "EXPECTED_ORDER_INVALID"}

        recomputed_order_sha256 = _digest(expected_order)
        if (
            recomputed_order_sha256 is None
            or recomputed_order_sha256 != expected_order_sha256
        ):
            return {**_safe_base(), "reason": "EXPECTED_ORDER_DIGEST_MISMATCH"}

        recomputed_event_sha256 = self._event_digest(
            canonical_attempt_id,
            event_type,
            None,
            None,
            None,
            event_time,
        )
        if (
            recomputed_event_sha256 is None
            or recomputed_event_sha256 != event_sha256
        ):
            return {**_safe_base(), "reason": "PREPARE_EVENT_DIGEST_MISMATCH"}

        envelope_payload = {
            "version": ENVELOPE_VERSION,
            "generated_at": current.isoformat(),
            "attempt_journal_version": JOURNAL_VERSION,
            "attempt_id": canonical_attempt_id,
            "authorization_id": authorization_id,
            "idempotency_key": idempotency_key,
            "contract_sha256": contract_sha256,
            "reservation_receipt_sha256": reservation_receipt_sha256,
            "intent_sha256": intent_sha256,
            "expected_order_sha256": expected_order_sha256,
            "paper_account_evidence_token": account_token,
            "order": {
                "symbol": expected_order["symbol"],
                "side": expected_order["side"],
                "asset_type": "STK",
                "order_type": "LMT",
                "time_in_force": "DAY",
                "quantity": expected_order["quantity"],
                "limit_price": float(expected_order["limit_price"]),
            },
            "constraints": {
                "mode": "PAPER",
                "live_execution_allowed": False,
                "automatic_retry_allowed": False,
                "automatic_cancel_allowed": False,
                "automatic_modify_allowed": False,
                "broker_order_object_allowed": False,
                "broker_request_materialization_allowed": False,
            },
        }
        envelope_sha256 = _digest(envelope_payload)
        if envelope_sha256 is None:
            return {**_safe_base(), "reason": "NON_CANONICAL_REVIEW_ENVELOPE"}

        return {
            **_safe_base(
                "ADAPTER_REVIEW_ENVELOPE_VALIDATED_NON_EXECUTABLE",
                "PREPARED_ATTEMPT_REVIEW_ENVELOPE_READY",
            ),
            **envelope_payload,
            "review_envelope_sha256": envelope_sha256,
            "prepared_age_seconds": age,
            "next_gate": "IBKR_PAPER_ADAPTER_IMPLEMENTATION_REVIEW_REQUIRED",
        }
