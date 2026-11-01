"""G6.16 persistent monotonic reconciliation ledger.

This module calls the G6.15 read-only reconciliation state machine and stores
accepted state transitions append-only. It never submits, cancels, modifies,
or retries broker orders.
"""

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sqlite3

from engines.paper_broker_reconciliation_state_machine import (
    reconcile_submission_attempt,
)


LEDGER_VERSION = "AURORA_G6_16_RECONCILIATION_LEDGER_V1"

PERSISTABLE_STATES = frozenset((
    "LOCAL_FAILURE_BEFORE_BROKER_DISPATCH",
    "BROKER_OUTCOME_UNKNOWN_DO_NOT_RETRY",
    "BROKER_SUBMISSION_PENDING",
    "BROKER_ORDER_OPEN_WORKING",
    "BROKER_ORDER_PARTIALLY_FILLED_WORKING",
    "BROKER_CANCEL_PENDING",
    "BROKER_ORDER_CANCELLED_UNFILLED",
    "BROKER_ORDER_PARTIALLY_FILLED_CANCELLED",
    "BROKER_ORDER_FILLED",
    "BROKER_ORDER_INACTIVE_MANUAL_REVIEW",
    "BROKER_WARNING_MANUAL_REVIEW",
    "BROKER_STATUS_UNKNOWN_MANUAL_REVIEW",
))

TERMINAL_STATES = frozenset((
    "LOCAL_FAILURE_BEFORE_BROKER_DISPATCH",
    "BROKER_ORDER_CANCELLED_UNFILLED",
    "BROKER_ORDER_PARTIALLY_FILLED_CANCELLED",
    "BROKER_ORDER_FILLED",
))

MANUAL_STATES = frozenset((
    "BROKER_ORDER_INACTIVE_MANUAL_REVIEW",
    "BROKER_WARNING_MANUAL_REVIEW",
    "BROKER_STATUS_UNKNOWN_MANUAL_REVIEW",
))

OBSERVED_NONTERMINAL = frozenset((
    "BROKER_SUBMISSION_PENDING",
    "BROKER_ORDER_OPEN_WORKING",
    "BROKER_ORDER_PARTIALLY_FILLED_WORKING",
    "BROKER_CANCEL_PENDING",
)) | MANUAL_STATES

ALLOWED_TRANSITIONS = {
    "BROKER_OUTCOME_UNKNOWN_DO_NOT_RETRY": OBSERVED_NONTERMINAL | TERMINAL_STATES,
    "BROKER_SUBMISSION_PENDING": OBSERVED_NONTERMINAL | TERMINAL_STATES,
    "BROKER_ORDER_OPEN_WORKING": frozenset((
        "BROKER_ORDER_OPEN_WORKING",
        "BROKER_ORDER_PARTIALLY_FILLED_WORKING",
        "BROKER_CANCEL_PENDING",
    )) | MANUAL_STATES | TERMINAL_STATES,
    "BROKER_ORDER_PARTIALLY_FILLED_WORKING": frozenset((
        "BROKER_ORDER_PARTIALLY_FILLED_WORKING",
        "BROKER_CANCEL_PENDING",
    )) | MANUAL_STATES | TERMINAL_STATES,
    "BROKER_CANCEL_PENDING": frozenset((
        "BROKER_CANCEL_PENDING",
        "BROKER_ORDER_OPEN_WORKING",
        "BROKER_ORDER_PARTIALLY_FILLED_WORKING",
    )) | MANUAL_STATES | TERMINAL_STATES,
    "BROKER_ORDER_INACTIVE_MANUAL_REVIEW": OBSERVED_NONTERMINAL | TERMINAL_STATES,
    "BROKER_WARNING_MANUAL_REVIEW": OBSERVED_NONTERMINAL | TERMINAL_STATES,
    "BROKER_STATUS_UNKNOWN_MANUAL_REVIEW": OBSERVED_NONTERMINAL | TERMINAL_STATES,
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS reconciliation_events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    attempt_id TEXT NOT NULL,
    authorization_id TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    contract_sha256 TEXT NOT NULL,
    reservation_receipt_sha256 TEXT NOT NULL,
    state TEXT NOT NULL,
    reason TEXT NOT NULL,
    evidence_time TEXT NOT NULL,
    perm_id INTEGER,
    client_id INTEGER,
    order_id INTEGER,
    broker_status TEXT,
    filled_quantity REAL,
    remaining_quantity REAL,
    attempt_sha256 TEXT NOT NULL,
    observation_sha256 TEXT NOT NULL,
    event_sha256 TEXT NOT NULL UNIQUE,
    recorded_at TEXT NOT NULL
)
"""


def _canonical_digest(payload):
    encoded = json.dumps(
        payload if payload is not None else None,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
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


def _safe_base(status="BLOCKED", reason="RECONCILIATION_LEDGER_BLOCKED"):
    return {
        "engine": "AURORA G6.16 Persistent Reconciliation Ledger",
        "ledger_version": LEDGER_VERSION,
        "status": status,
        "reason": reason,
        "ledger_recorded": False,
        "automatic_retry_allowed": False,
        "same_authorization_retry_allowed": False,
        "broker_submission_allowed": False,
        "paper_order_submission_allowed": False,
        "live_execution_allowed": False,
        "automatic_cancel_allowed": False,
        "automatic_modify_allowed": False,
        "broker_order_object_allowed": False,
    }


def _evidence_time(attempt, broker_observation):
    if isinstance(broker_observation, dict):
        observed = _utc_datetime(
            broker_observation.get("snapshot_generated_at_utc")
        )
        if observed is not None:
            return observed
    if isinstance(attempt, dict):
        return _utc_datetime(attempt.get("attempted_at"))
    return None


def _identity_from_inputs(reservation, attempt):
    if not isinstance(reservation, dict) or not isinstance(attempt, dict):
        return None
    values = {
        "attempt_id": str(attempt.get("attempt_id") or ""),
        "authorization_id": str(reservation.get("authorization_id") or ""),
        "idempotency_key": str(reservation.get("idempotency_key") or ""),
        "contract_sha256": str(reservation.get("contract_sha256") or ""),
        "reservation_receipt_sha256": str(
            reservation.get("reservation_receipt_sha256") or ""
        ),
    }
    if not all(values.values()):
        return None
    return values


def _transition_allowed(previous, current):
    if previous == current:
        return True
    if previous in TERMINAL_STATES:
        return False
    return current in ALLOWED_TRANSITIONS.get(previous, frozenset())


class PaperReconciliationLedger:
    """Append-only monotonic state history for one future Paper attempt."""

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

    def record(
        self,
        reservation,
        attempt,
        broker_observation=None,
        now=None,
    ):
        current = _utc_datetime(now)
        if now is not None and current is None:
            return {
                **_safe_base(),
                "reason": "INVALID_EVALUATION_TIME",
            }
        current = current or datetime.now(timezone.utc)

        result = reconcile_submission_attempt(
            reservation,
            attempt=attempt,
            broker_observation=broker_observation,
            now=current,
        )

        state = result.get("status")
        if state == "BLOCKED":
            return {
                **_safe_base(),
                "reason": "G6_15_RECONCILIATION_BLOCKED",
                "upstream_reason": result.get("reason"),
            }
        if state == "RESERVED_NO_SUBMISSION_ATTEMPT":
            return {
                **_safe_base(
                    "NOT_RECORDED",
                    "NO_ATTEMPT_IDENTITY_TO_PERSIST",
                ),
                "upstream_state": state,
            }
        if state not in PERSISTABLE_STATES:
            return {
                **_safe_base(),
                "reason": "UNSUPPORTED_RECONCILIATION_STATE",
                "upstream_state": state,
            }

        identity = _identity_from_inputs(reservation, attempt)
        evidence_time = _evidence_time(attempt, broker_observation)
        if identity is None or evidence_time is None:
            return {
                **_safe_base(),
                "reason": "INCOMPLETE_RECONCILIATION_IDENTITY",
            }

        attempt_sha256 = _canonical_digest(attempt)
        observation_sha256 = _canonical_digest(broker_observation)
        event_payload = {
            **identity,
            "state": state,
            "reason": result.get("reason"),
            "evidence_time": evidence_time.isoformat(),
            "perm_id": result.get("perm_id"),
            "client_id": result.get("client_id"),
            "order_id": result.get("order_id"),
            "broker_status": result.get("broker_status"),
            "filled_quantity": result.get("filled_quantity"),
            "remaining_quantity": result.get("remaining_quantity"),
            "attempt_sha256": attempt_sha256,
            "observation_sha256": observation_sha256,
        }
        event_sha256 = _canonical_digest(event_payload)
        recorded_at = current.isoformat()

        try:
            connection = self._connect()
        except (OSError, sqlite3.Error):
            return {
                **_safe_base(),
                "reason": "RECONCILIATION_LEDGER_UNAVAILABLE",
            }

        try:
            connection.execute("BEGIN IMMEDIATE")
            previous = connection.execute(
                """
                SELECT
                    authorization_id,
                    idempotency_key,
                    contract_sha256,
                    reservation_receipt_sha256,
                    state,
                    evidence_time,
                    perm_id,
                    client_id,
                    order_id,
                    filled_quantity,
                    remaining_quantity,
                    event_sha256
                FROM reconciliation_events
                WHERE attempt_id = ?
                ORDER BY event_id DESC
                LIMIT 1
                """,
                (identity["attempt_id"],),
            ).fetchone()

            if previous is not None:
                (
                    prev_auth,
                    prev_key,
                    prev_contract,
                    prev_receipt,
                    prev_state,
                    prev_time_text,
                    prev_perm,
                    prev_client,
                    prev_order,
                    prev_filled,
                    prev_remaining,
                    prev_event_sha,
                ) = previous

                if (
                    prev_auth != identity["authorization_id"]
                    or prev_key != identity["idempotency_key"]
                    or prev_contract != identity["contract_sha256"]
                    or prev_receipt != identity["reservation_receipt_sha256"]
                ):
                    connection.execute("ROLLBACK")
                    return {
                        **_safe_base(),
                        "reason": "ATTEMPT_IDENTITY_CHANGED",
                    }

                if prev_event_sha == event_sha256:
                    connection.execute("ROLLBACK")
                    return {
                        **_safe_base(
                            "RECONCILIATION_EVENT_ALREADY_RECORDED",
                            "IDEMPOTENT_DUPLICATE_EVENT",
                        ),
                        "ledger_recorded": False,
                        "duplicate": True,
                        "attempt_id": identity["attempt_id"],
                        "reconciliation_state": prev_state,
                        "event_sha256": prev_event_sha,
                    }

                prev_time = _utc_datetime(prev_time_text)
                if prev_time is None or evidence_time < prev_time:
                    connection.execute("ROLLBACK")
                    return {
                        **_safe_base(),
                        "reason": "STALE_STATE_REGRESSION_BLOCKED",
                        "previous_state": prev_state,
                        "proposed_state": state,
                    }

                if prev_state in TERMINAL_STATES:
                    connection.execute("ROLLBACK")
                    return {
                        **_safe_base(
                            "TERMINAL_STATE_IMMUTABLE",
                            "TERMINAL_RECONCILIATION_ALREADY_RECORDED",
                        ),
                        "previous_state": prev_state,
                        "proposed_state": state,
                    }

                if not _transition_allowed(prev_state, state):
                    connection.execute("ROLLBACK")
                    return {
                        **_safe_base(),
                        "reason": "INVALID_STATE_TRANSITION",
                        "previous_state": prev_state,
                        "proposed_state": state,
                    }

                for previous_value, new_value, field in (
                    (prev_perm, result.get("perm_id"), "perm_id"),
                    (prev_client, result.get("client_id"), "client_id"),
                    (prev_order, result.get("order_id"), "order_id"),
                ):
                    if (
                        previous_value is not None
                        and new_value is not None
                        and previous_value != new_value
                    ):
                        connection.execute("ROLLBACK")
                        return {
                            **_safe_base(),
                            "reason": "BROKER_IDENTITY_REGRESSION_BLOCKED",
                            "field": field,
                        }
                    if previous_value is not None and new_value is None:
                        connection.execute("ROLLBACK")
                        return {
                            **_safe_base(),
                            "reason": "BROKER_IDENTITY_EVIDENCE_DISAPPEARED",
                            "field": field,
                        }

                new_filled = result.get("filled_quantity")
                if (
                    prev_filled is not None
                    and new_filled is not None
                    and float(new_filled) + 1e-7 < float(prev_filled)
                ):
                    connection.execute("ROLLBACK")
                    return {
                        **_safe_base(),
                        "reason": "FILLED_QUANTITY_REGRESSION_BLOCKED",
                    }
                if prev_filled is not None and new_filled is None:
                    connection.execute("ROLLBACK")
                    return {
                        **_safe_base(),
                        "reason": "FILL_EVIDENCE_DISAPPEARED",
                    }

                if (
                    prev_remaining is not None
                    and result.get("remaining_quantity") is not None
                    and state not in MANUAL_STATES
                    and float(result["remaining_quantity"]) > float(prev_remaining) + 1e-7
                ):
                    connection.execute("ROLLBACK")
                    return {
                        **_safe_base(),
                        "reason": "REMAINING_QUANTITY_REGRESSION_BLOCKED",
                    }

            try:
                connection.execute(
                    """
                    INSERT INTO reconciliation_events (
                        attempt_id,
                        authorization_id,
                        idempotency_key,
                        contract_sha256,
                        reservation_receipt_sha256,
                        state,
                        reason,
                        evidence_time,
                        perm_id,
                        client_id,
                        order_id,
                        broker_status,
                        filled_quantity,
                        remaining_quantity,
                        attempt_sha256,
                        observation_sha256,
                        event_sha256,
                        recorded_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        identity["attempt_id"],
                        identity["authorization_id"],
                        identity["idempotency_key"],
                        identity["contract_sha256"],
                        identity["reservation_receipt_sha256"],
                        state,
                        result.get("reason"),
                        evidence_time.isoformat(),
                        result.get("perm_id"),
                        result.get("client_id"),
                        result.get("order_id"),
                        result.get("broker_status"),
                        result.get("filled_quantity"),
                        result.get("remaining_quantity"),
                        attempt_sha256,
                        observation_sha256,
                        event_sha256,
                        recorded_at,
                    ),
                )
                connection.execute("COMMIT")
            except sqlite3.IntegrityError:
                connection.execute("ROLLBACK")
                return {
                    **_safe_base(
                        "RECONCILIATION_EVENT_ALREADY_RECORDED",
                        "EVENT_DIGEST_ALREADY_EXISTS",
                    ),
                    "duplicate": True,
                    "attempt_id": identity["attempt_id"],
                    "event_sha256": event_sha256,
                }
            except sqlite3.Error:
                connection.execute("ROLLBACK")
                return {
                    **_safe_base(),
                    "reason": "RECONCILIATION_LEDGER_UNAVAILABLE",
                }
        finally:
            connection.close()

        return {
            **_safe_base(
                "RECONCILIATION_EVENT_RECORDED_NON_EXECUTABLE",
                "MONOTONIC_RECONCILIATION_STATE_PERSISTED",
            ),
            "ledger_recorded": True,
            "duplicate": False,
            "attempt_id": identity["attempt_id"],
            "authorization_id": identity["authorization_id"],
            "reconciliation_state": state,
            "evidence_time": evidence_time.isoformat(),
            "event_sha256": event_sha256,
            "recorded_at": recorded_at,
            "terminal_state": state in TERMINAL_STATES,
            "next_action": (
                "NO_RETRY_FINALIZE_AUDIT"
                if state in TERMINAL_STATES
                else "REFRESH_READ_ONLY_BROKER_EVIDENCE_AND_MANUALLY_RECONCILE"
            ),
        }
