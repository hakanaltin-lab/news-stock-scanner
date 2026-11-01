"""G6.17 trusted submission-attempt journal.

This module creates and persists non-executable attempt artifacts for G6.15.
It does not connect to a broker and cannot submit, cancel, modify, or retry an
order. A DISPATCH_CLAIM event is an adapter-side journal claim only; broker
side effects still require independent read-only reconciliation.
"""

from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import sqlite3
from uuid import UUID, uuid4

from engines.paper_submission_contract import CONTRACT_VERSION
from engines.paper_authorization_reservation_ledger import (
    LEDGER_VERSION as RESERVATION_LEDGER_VERSION,
)


JOURNAL_VERSION = "AURORA_G6_17_SUBMISSION_ATTEMPT_JOURNAL_V1"
DEFAULT_MAX_RESERVATION_AGE_SECONDS = 60

REGISTRY_SCHEMA = """
CREATE TABLE IF NOT EXISTS submission_attempt_registry (
    attempt_id TEXT PRIMARY KEY,
    authorization_id TEXT NOT NULL UNIQUE,
    idempotency_key TEXT NOT NULL UNIQUE,
    contract_sha256 TEXT NOT NULL UNIQUE,
    reservation_receipt_sha256 TEXT NOT NULL UNIQUE,
    intent_sha256 TEXT NOT NULL,
    expected_order_json TEXT NOT NULL,
    expected_order_sha256 TEXT NOT NULL,
    paper_account_evidence_token TEXT NOT NULL,
    prepared_at TEXT NOT NULL
)
"""

EVENT_SCHEMA = """
CREATE TABLE IF NOT EXISTS submission_attempt_events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    attempt_id TEXT NOT NULL,
    event_type TEXT NOT NULL
        CHECK (event_type IN (
            'PREPARED_NON_EXECUTABLE',
            'LOCAL_FAILURE_BEFORE_DISPATCH',
            'DISPATCH_CLAIM_RECORDED'
        )),
    client_id INTEGER,
    order_id INTEGER,
    evidence_sha256 TEXT,
    event_time TEXT NOT NULL,
    event_sha256 TEXT NOT NULL UNIQUE,
    FOREIGN KEY(attempt_id) REFERENCES submission_attempt_registry(attempt_id)
)
"""


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


def _valid_sha256(value):
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(c in "0123456789abcdef" for c in value)
    )


def _uuid4(value):
    text = str(value or "").strip()
    try:
        parsed = UUID(text)
    except (ValueError, AttributeError):
        return None
    return text if parsed.version == 4 and str(parsed) == text else None


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


def _valid_symbol(value):
    return (
        isinstance(value, str)
        and value.isascii()
        and 1 <= len(value) <= 10
        and all(c.isupper() or c.isdigit() or c in ".-" for c in value)
    )


def _valid_idempotency_key(value):
    return (
        isinstance(value, str)
        and 8 <= len(value) <= 128
        and value.isascii()
        and all(c.isalnum() or c in "-_" for c in value)
    )


def _valid_account_token(value):
    return (
        isinstance(value, str)
        and value.startswith("IBKR-EVID-")
        and len(value) == 26
        and all(c in "0123456789ABCDEF" for c in value[10:])
    )


def _normalize_intent(intent):
    if not isinstance(intent, dict):
        return None
    required = {
        "symbol",
        "side",
        "order_type",
        "quantity",
        "limit_price",
        "idempotency_key",
    }
    if set(intent) != required:
        return None
    symbol = intent.get("symbol")
    side = intent.get("side")
    order_type = intent.get("order_type")
    quantity = intent.get("quantity")
    limit_price = intent.get("limit_price")
    key = intent.get("idempotency_key")
    if (
        not _valid_symbol(symbol)
        or side not in ("BUY", "SELL")
        or order_type != "LMT"
        or type(quantity) is not int
        or quantity <= 0
        or type(limit_price) not in (int, float)
        or not math.isfinite(limit_price)
        or limit_price <= 0
        or not _valid_idempotency_key(key)
    ):
        return None
    return {
        "symbol": symbol,
        "side": side,
        "order_type": "LMT",
        "quantity": quantity,
        "limit_price": float(limit_price),
        "idempotency_key": key,
    }


def _contract_payload(contract):
    return {
        "version": contract.get("version"),
        "generated_at": contract.get("generated_at"),
        "authorization_id": contract.get("authorization_id"),
        "intent_sha256": contract.get("intent_sha256"),
        "shadow_order_sha256": contract.get("shadow_order_sha256"),
        "idempotency_key": contract.get("idempotency_key"),
    }


def _safe_base(status="BLOCKED", reason="ATTEMPT_JOURNAL_BLOCKED"):
    return {
        "engine": "AURORA G6.17 Submission Attempt Journal",
        "journal_version": JOURNAL_VERSION,
        "status": status,
        "reason": reason,
        "broker_submission_allowed": False,
        "paper_order_submission_allowed": False,
        "live_execution_allowed": False,
        "automatic_retry_allowed": False,
        "same_authorization_retry_allowed": False,
        "automatic_cancel_allowed": False,
        "automatic_modify_allowed": False,
        "broker_order_object_allowed": False,
    }


def _validate_prepare_inputs(
    reservation,
    submission_contract,
    intent,
    account_token,
    now,
    max_reservation_age_seconds,
):
    if not all(isinstance(x, dict) for x in (
        reservation,
        submission_contract,
        intent,
    )):
        return None, "INVALID_PREPARE_INPUT"

    normalized = _normalize_intent(intent)
    if normalized is None:
        return None, "INVALID_INTENT"

    if not _valid_account_token(account_token):
        return None, "INVALID_ACCOUNT_EVIDENCE_TOKEN"

    if (
        reservation.get("status")
        != "AUTHORIZATION_RESERVED_NON_EXECUTABLE"
        or reservation.get("reason")
        != "AT_MOST_ONCE_RESERVATION_RECORDED"
        or reservation.get("reserved") is not True
        or reservation.get("reservation_state")
        != "RESERVED_NON_EXECUTABLE"
        or reservation.get("paper_order_submission_allowed") is not False
        or reservation.get("live_execution_allowed") is not False
        or reservation.get("broker_submission_allowed") is not False
        or reservation.get("automatic_promotion_allowed") is not False
        or reservation.get("real_money_trading_allowed") is not False
        or reservation.get("broker_order_object_allowed") is not False
    ):
        return None, "INVALID_RESERVATION"

    reserved_at = _utc_datetime(reservation.get("reserved_at"))
    if reserved_at is None:
        return None, "INVALID_RESERVATION_TIME"
    reservation_age = (now - reserved_at).total_seconds()
    if (
        reservation_age < 0
        or reservation_age > float(max_reservation_age_seconds)
    ):
        return None, "RESERVATION_STALE"

    authorization_id = _uuid4(reservation.get("authorization_id"))
    if authorization_id is None:
        return None, "INVALID_AUTHORIZATION_ID"

    intent_sha256 = _digest(normalized)
    if intent_sha256 is None:
        return None, "NON_CANONICAL_INTENT"

    contract_sha256 = reservation.get("contract_sha256")
    receipt_sha256 = reservation.get("reservation_receipt_sha256")
    if not _valid_sha256(contract_sha256) or not _valid_sha256(receipt_sha256):
        return None, "INVALID_RESERVATION_DIGEST"

    if (
        submission_contract.get("status")
        != "SUBMISSION_CONTRACT_VALIDATED_NON_EXECUTABLE"
        or submission_contract.get("reason")
        != "ARTIFACTS_BOUND_BUT_BROKER_PERMISSION_NOT_GRANTED"
        or submission_contract.get("version") != CONTRACT_VERSION
        or submission_contract.get("authorization_id") != authorization_id
        or submission_contract.get("idempotency_key")
        != normalized["idempotency_key"]
        or submission_contract.get("intent_sha256") != intent_sha256
        or submission_contract.get("contract_sha256") != contract_sha256
        or submission_contract.get("paper_order_submission_allowed") is not False
        or submission_contract.get("live_execution_allowed") is not False
        or submission_contract.get("broker_submission_allowed") is not False
        or submission_contract.get("automatic_promotion_allowed") is not False
        or submission_contract.get("real_money_trading_allowed") is not False
        or submission_contract.get("broker_order_object_allowed") is not False
        or submission_contract.get("next_gate")
        != "PAPER_BROKER_ADAPTER_CODE_REVIEW_REQUIRED"
        or submission_contract.get(
            "authorization_id_must_be_atomically_consumed_before_submission"
        ) is not True
    ):
        return None, "CONTRACT_RESERVATION_INTENT_MISMATCH"

    expected_contract_sha256 = _digest(_contract_payload(submission_contract))
    if (
        expected_contract_sha256 is None
        or submission_contract.get("contract_sha256")
        != expected_contract_sha256
    ):
        return None, "CONTRACT_DIGEST_MISMATCH"

    if (
        reservation.get("authorization_id") != authorization_id
        or reservation.get("idempotency_key") != normalized["idempotency_key"]
    ):
        return None, "RESERVATION_IDENTITY_MISMATCH"

    expected_order = {
        "symbol": normalized["symbol"],
        "side": normalized["side"],
        "quantity": normalized["quantity"],
        "limit_price": normalized["limit_price"],
    }
    expected_order_sha256 = _digest(expected_order)
    if expected_order_sha256 is None:
        return None, "NON_CANONICAL_EXPECTED_ORDER"

    return {
        "authorization_id": authorization_id,
        "idempotency_key": normalized["idempotency_key"],
        "contract_sha256": contract_sha256,
        "reservation_receipt_sha256": receipt_sha256,
        "intent_sha256": intent_sha256,
        "expected_order": expected_order,
        "expected_order_sha256": expected_order_sha256,
        "paper_account_evidence_token": account_token,
        "shadow_order_sha256": submission_contract.get("shadow_order_sha256"),
        "contract_generated_at": submission_contract.get("generated_at"),
    }, None


class PaperSubmissionAttemptJournal:
    """Immutable attempt registry plus append-only attempt lifecycle events."""

    def __init__(self, path, reservation_ledger_path):
        self.path = Path(path)
        self.reservation_ledger_path = Path(reservation_ledger_path)

    def _connect(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(
            str(self.path),
            timeout=10.0,
            isolation_level=None,
        )
        connection.execute("PRAGMA busy_timeout = 10000")
        connection.execute("PRAGMA synchronous = FULL")
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute(REGISTRY_SCHEMA)
        connection.execute(EVENT_SCHEMA)
        os.chmod(self.path, 0o600)
        return connection

    def _verify_persisted_reservation(self, reservation, prepared):
        if not self.reservation_ledger_path.exists():
            return False, "RESERVATION_LEDGER_EVIDENCE_REQUIRED"
        try:
            connection = sqlite3.connect(
                f"file:{self.reservation_ledger_path}?mode=ro",
                uri=True,
                timeout=5.0,
            )
        except sqlite3.Error:
            return False, "RESERVATION_LEDGER_UNAVAILABLE"
        try:
            row = connection.execute(
                """
                SELECT
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
                FROM paper_authorization_reservations
                WHERE authorization_id = ?
                """,
                (prepared["authorization_id"],),
            ).fetchone()
        except sqlite3.Error:
            return False, "RESERVATION_LEDGER_UNAVAILABLE"
        finally:
            connection.close()

        if row is None:
            return False, "RESERVATION_NOT_FOUND_IN_LEDGER"

        (
            authorization_id,
            idempotency_key,
            shadow_sha256,
            intent_sha256,
            contract_sha256,
            contract_version,
            contract_generated_at,
            reservation_state,
            reserved_at,
            receipt_sha256,
        ) = row

        receipt_payload = {
            "ledger_version": RESERVATION_LEDGER_VERSION,
            "authorization_id": authorization_id,
            "idempotency_key": idempotency_key,
            "shadow_order_sha256": shadow_sha256,
            "intent_sha256": intent_sha256,
            "contract_sha256": contract_sha256,
            "contract_version": contract_version,
            "contract_generated_at": contract_generated_at,
            "reservation_state": reservation_state,
            "reserved_at": reserved_at,
        }
        expected_receipt = _digest(receipt_payload)
        if expected_receipt is None or expected_receipt != receipt_sha256:
            return False, "RESERVATION_LEDGER_RECEIPT_CORRUPTED"

        if (
            authorization_id != prepared["authorization_id"]
            or idempotency_key != prepared["idempotency_key"]
            or shadow_sha256 != prepared["shadow_order_sha256"]
            or intent_sha256 != prepared["intent_sha256"]
            or contract_sha256 != prepared["contract_sha256"]
            or contract_version != CONTRACT_VERSION
            or contract_generated_at != prepared["contract_generated_at"]
            or reservation_state != "RESERVED_NON_EXECUTABLE"
            or receipt_sha256 != prepared["reservation_receipt_sha256"]
            or reserved_at != reservation.get("reserved_at")
        ):
            return False, "RESERVATION_LEDGER_BINDING_MISMATCH"

        return True, None

    @staticmethod
    def _event_digest(attempt_id, event_type, client_id, order_id, evidence, event_time):
        return _digest({
            "attempt_id": attempt_id,
            "event_type": event_type,
            "client_id": client_id,
            "order_id": order_id,
            "evidence_sha256": evidence,
            "event_time": event_time,
        })

    @staticmethod
    def _artifact_from_rows(registry, event):
        (
            attempt_id,
            authorization_id,
            idempotency_key,
            contract_sha256,
            reservation_receipt_sha256,
            _intent_sha256,
            expected_order_json,
            _expected_order_sha256,
            account_token,
            _prepared_at,
        ) = registry
        (
            _event_id,
            _attempt_id,
            event_type,
            client_id,
            order_id,
            evidence_sha256,
            event_time,
            event_sha256,
        ) = event

        if event_type == "PREPARED_NON_EXECUTABLE":
            return {
                **_safe_base(
                    "ATTEMPT_PREPARED_NON_EXECUTABLE",
                    "NO_DISPATCH_OR_FAILURE_EVENT_RECORDED",
                ),
                "attempt_id": attempt_id,
                "attempt_artifact_available": False,
                "event_sha256": event_sha256,
            }

        request_dispatched = event_type == "DISPATCH_CLAIM_RECORDED"
        local_failure = event_type == "LOCAL_FAILURE_BEFORE_DISPATCH"
        artifact = {
            "status": "SUBMISSION_ATTEMPT_RECORDED",
            "attempt_id": attempt_id,
            "mode": "PAPER",
            "attempted_at": event_time,
            "authorization_id": authorization_id,
            "idempotency_key": idempotency_key,
            "contract_sha256": contract_sha256,
            "reservation_receipt_sha256": reservation_receipt_sha256,
            "request_dispatched": request_dispatched,
            "local_failure_before_dispatch": local_failure,
            "expected_order": json.loads(expected_order_json),
            "client_id": client_id,
            "order_id": order_id,
            "paper_account_evidence_token": account_token,
            "automatic_retry_allowed": False,
            "live_execution_allowed": False,
            "paper_order_submission_allowed": False,
            "broker_order_object_allowed": False,
            "attempt_journal_event_sha256": event_sha256,
            "dispatch_or_failure_evidence_sha256": evidence_sha256,
            "attempt_journal_version": JOURNAL_VERSION,
        }
        return {
            **_safe_base(
                "ATTEMPT_ARTIFACT_READY_NON_EXECUTABLE",
                "PERSISTED_ATTEMPT_EVENT_NORMALIZED",
            ),
            "attempt_artifact_available": True,
            "attempt_artifact": artifact,
            "attempt_id": attempt_id,
            "event_type": event_type,
            "event_sha256": event_sha256,
        }

    @staticmethod
    def _load_registry(connection, attempt_id):
        return connection.execute(
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
            (attempt_id,),
        ).fetchone()

    @staticmethod
    def _latest_event(connection, attempt_id):
        return connection.execute(
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
            (attempt_id,),
        ).fetchone()

    def prepare(
        self,
        reservation,
        submission_contract,
        intent,
        paper_account_evidence_token,
        now=None,
        attempt_id=None,
        max_reservation_age_seconds=DEFAULT_MAX_RESERVATION_AGE_SECONDS,
    ):
        current = _utc_datetime(now)
        if now is not None and current is None:
            return {**_safe_base(), "reason": "INVALID_EVALUATION_TIME"}
        current = current or datetime.now(timezone.utc)

        prepared, error = _validate_prepare_inputs(
            reservation,
            submission_contract,
            intent,
            paper_account_evidence_token,
            current,
            max_reservation_age_seconds,
        )
        if error:
            return {**_safe_base(), "reason": error}

        persisted, persisted_error = self._verify_persisted_reservation(
            reservation,
            prepared,
        )
        if not persisted:
            return {
                **_safe_base(),
                "reason": persisted_error,
            }

        requested_attempt_id = (
            _uuid4(attempt_id)
            if attempt_id is not None
            else str(uuid4())
        )
        if requested_attempt_id is None:
            return {**_safe_base(), "reason": "INVALID_ATTEMPT_ID"}

        prepared_at = current.isoformat()
        expected_order_json = json.dumps(
            prepared["expected_order"],
            sort_keys=True,
            separators=(",", ":"),
        )
        event_sha256 = self._event_digest(
            requested_attempt_id,
            "PREPARED_NON_EXECUTABLE",
            None,
            None,
            None,
            prepared_at,
        )
        if event_sha256 is None:
            return {**_safe_base(), "reason": "NON_CANONICAL_PREPARE_EVENT"}

        try:
            connection = self._connect()
        except (OSError, sqlite3.Error):
            return {**_safe_base(), "reason": "ATTEMPT_JOURNAL_UNAVAILABLE"}

        try:
            connection.execute("BEGIN IMMEDIATE")
            try:
                connection.execute(
                    """
                    INSERT INTO submission_attempt_registry (
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
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        requested_attempt_id,
                        prepared["authorization_id"],
                        prepared["idempotency_key"],
                        prepared["contract_sha256"],
                        prepared["reservation_receipt_sha256"],
                        prepared["intent_sha256"],
                        expected_order_json,
                        prepared["expected_order_sha256"],
                        prepared["paper_account_evidence_token"],
                        prepared_at,
                    ),
                )
                connection.execute(
                    """
                    INSERT INTO submission_attempt_events (
                        attempt_id,
                        event_type,
                        client_id,
                        order_id,
                        evidence_sha256,
                        event_time,
                        event_sha256
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        requested_attempt_id,
                        "PREPARED_NON_EXECUTABLE",
                        None,
                        None,
                        None,
                        prepared_at,
                        event_sha256,
                    ),
                )
                connection.execute("COMMIT")
            except sqlite3.IntegrityError:
                connection.execute("ROLLBACK")
                existing = connection.execute(
                    """
                    SELECT attempt_id
                    FROM submission_attempt_registry
                    WHERE authorization_id = ?
                       OR idempotency_key = ?
                       OR contract_sha256 = ?
                       OR reservation_receipt_sha256 = ?
                    LIMIT 1
                    """,
                    (
                        prepared["authorization_id"],
                        prepared["idempotency_key"],
                        prepared["contract_sha256"],
                        prepared["reservation_receipt_sha256"],
                    ),
                ).fetchone()
                return {
                    **_safe_base(
                        "ATTEMPT_ALREADY_EXISTS",
                        "AUTHORIZATION_OR_ORDER_ALREADY_PREPARED",
                    ),
                    "attempt_id": existing[0] if existing else None,
                    "duplicate": True,
                }
            except sqlite3.Error:
                connection.execute("ROLLBACK")
                return {**_safe_base(), "reason": "ATTEMPT_JOURNAL_UNAVAILABLE"}
        finally:
            connection.close()

        return {
            **_safe_base(
                "ATTEMPT_PREPARED_NON_EXECUTABLE",
                "PREPARE_EVENT_PERSISTED",
            ),
            "attempt_id": requested_attempt_id,
            "attempt_artifact_available": False,
            "prepared_at": prepared_at,
            "event_sha256": event_sha256,
        }

    def _finalize(
        self,
        attempt_id,
        event_type,
        now,
        evidence_sha256,
        client_id=None,
        order_id=None,
    ):
        canonical_id = _uuid4(attempt_id)
        current = _utc_datetime(now)
        if canonical_id is None:
            return {**_safe_base(), "reason": "INVALID_ATTEMPT_ID"}
        if now is not None and current is None:
            return {**_safe_base(), "reason": "INVALID_EVALUATION_TIME"}
        current = current or datetime.now(timezone.utc)
        if not _valid_sha256(evidence_sha256):
            return {**_safe_base(), "reason": "INVALID_EVENT_EVIDENCE_DIGEST"}

        if event_type == "DISPATCH_CLAIM_RECORDED":
            if (
                type(client_id) is not int
                or client_id < 0
                or type(order_id) is not int
                or order_id < 0
            ):
                return {**_safe_base(), "reason": "INVALID_BROKER_REQUEST_IDENTITY"}
        else:
            if client_id is not None or order_id is not None:
                return {**_safe_base(), "reason": "UNEXPECTED_BROKER_REQUEST_IDENTITY"}

        event_time = current.isoformat()
        event_sha256 = self._event_digest(
            canonical_id,
            event_type,
            client_id,
            order_id,
            evidence_sha256,
            event_time,
        )
        if event_sha256 is None:
            return {**_safe_base(), "reason": "NON_CANONICAL_ATTEMPT_EVENT"}

        try:
            connection = self._connect()
        except (OSError, sqlite3.Error):
            return {**_safe_base(), "reason": "ATTEMPT_JOURNAL_UNAVAILABLE"}

        try:
            connection.execute("BEGIN IMMEDIATE")
            registry = self._load_registry(connection, canonical_id)
            if registry is None:
                connection.execute("ROLLBACK")
                return {**_safe_base(), "reason": "ATTEMPT_NOT_PREPARED"}

            latest = self._latest_event(connection, canonical_id)
            if latest is None:
                connection.execute("ROLLBACK")
                return {**_safe_base(), "reason": "ATTEMPT_EVENT_HISTORY_MISSING"}

            latest_type = latest[2]
            prepared_at = _utc_datetime(registry[9])
            if prepared_at is None or current < prepared_at:
                connection.execute("ROLLBACK")
                return {**_safe_base(), "reason": "ATTEMPT_EVENT_PREDATES_PREPARE"}

            if latest_type != "PREPARED_NON_EXECUTABLE":
                same_final = (
                    latest_type == event_type
                    and latest[3] == client_id
                    and latest[4] == order_id
                    and latest[5] == evidence_sha256
                )
                connection.execute("ROLLBACK")
                if same_final:
                    return {
                        **self._artifact_from_rows(registry, latest),
                        "duplicate": True,
                    }
                return {
                    **_safe_base(
                        "ATTEMPT_FINALIZED",
                        "ATTEMPT_ALREADY_HAS_FINAL_BOUNDARY_EVENT",
                    ),
                    "attempt_id": canonical_id,
                    "existing_event_type": latest_type,
                }

            try:
                connection.execute(
                    """
                    INSERT INTO submission_attempt_events (
                        attempt_id,
                        event_type,
                        client_id,
                        order_id,
                        evidence_sha256,
                        event_time,
                        event_sha256
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        canonical_id,
                        event_type,
                        client_id,
                        order_id,
                        evidence_sha256,
                        event_time,
                        event_sha256,
                    ),
                )
                connection.execute("COMMIT")
            except sqlite3.IntegrityError:
                connection.execute("ROLLBACK")
                return {
                    **_safe_base(
                        "ATTEMPT_EVENT_ALREADY_RECORDED",
                        "EVENT_DIGEST_ALREADY_EXISTS",
                    ),
                    "attempt_id": canonical_id,
                    "duplicate": True,
                }
            except sqlite3.Error:
                connection.execute("ROLLBACK")
                return {**_safe_base(), "reason": "ATTEMPT_JOURNAL_UNAVAILABLE"}

            latest = self._latest_event(connection, canonical_id)
        finally:
            connection.close()

        result = self._artifact_from_rows(registry, latest)
        result["duplicate"] = False
        return result

    def record_local_failure_before_dispatch(
        self,
        attempt_id,
        failure_evidence_sha256,
        now=None,
    ):
        return self._finalize(
            attempt_id,
            "LOCAL_FAILURE_BEFORE_DISPATCH",
            now,
            failure_evidence_sha256,
        )

    def record_dispatch_claim(
        self,
        attempt_id,
        client_id,
        order_id,
        dispatch_evidence_sha256,
        now=None,
    ):
        return self._finalize(
            attempt_id,
            "DISPATCH_CLAIM_RECORDED",
            now,
            dispatch_evidence_sha256,
            client_id=client_id,
            order_id=order_id,
        )

    def get_attempt_artifact(self, attempt_id):
        canonical_id = _uuid4(attempt_id)
        if canonical_id is None:
            return {**_safe_base(), "reason": "INVALID_ATTEMPT_ID"}
        try:
            connection = self._connect()
        except (OSError, sqlite3.Error):
            return {**_safe_base(), "reason": "ATTEMPT_JOURNAL_UNAVAILABLE"}
        try:
            registry = self._load_registry(connection, canonical_id)
            latest = self._latest_event(connection, canonical_id)
        finally:
            connection.close()
        if registry is None or latest is None:
            return {**_safe_base(), "reason": "ATTEMPT_NOT_FOUND"}
        return self._artifact_from_rows(registry, latest)
