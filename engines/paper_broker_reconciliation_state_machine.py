"""G6.15 broker failure and reconciliation state machine.

This module is broker-independent and read-only. It never submits, cancels,
modifies, or retries an order. It classifies a future Paper submission attempt
using a G6.14 reservation plus read-only broker observation evidence.
"""

from datetime import datetime, timezone
import hmac
import math
from uuid import UUID


STATE_MACHINE_VERSION = "AURORA_G6_15_RECONCILIATION_V1"
DEFAULT_MAX_OBSERVATION_AGE_SECONDS = 60

ACTIVE_STATUSES = frozenset(("PreSubmitted", "Submitted"))
PENDING_STATUSES = frozenset(("PendingSubmit",))
CANCEL_PENDING_STATUSES = frozenset(("PendingCancel", "PreCancelled"))
TERMINAL_STATUSES = frozenset(("Filled", "Cancelled", "Inactive"))
MANUAL_REVIEW_STATUSES = frozenset(("WarnState",))
SUPPORTED_BROKER_STATUSES = (
    ACTIVE_STATUSES
    | PENDING_STATUSES
    | CANCEL_PENDING_STATUSES
    | TERMINAL_STATUSES
    | MANUAL_REVIEW_STATUSES
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


def _nonnegative_number(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def _positive_number(value):
    return type(value) in (int, float) and math.isfinite(value) and value > 0


def _valid_symbol(value):
    return (
        isinstance(value, str)
        and value.isascii()
        and 1 <= len(value) <= 10
        and all(c.isupper() or c.isdigit() or c in ".-" for c in value)
    )


def _base(status="BLOCKED", reason="RECONCILIATION_BLOCKED"):
    return {
        "engine": "AURORA G6.15 Broker Failure & Reconciliation State Machine",
        "version": STATE_MACHINE_VERSION,
        "status": status,
        "reason": reason,
        "automatic_retry_allowed": False,
        "same_authorization_retry_allowed": False,
        "broker_submission_allowed": False,
        "paper_order_submission_allowed": False,
        "live_execution_allowed": False,
        "automatic_cancel_allowed": False,
        "automatic_modify_allowed": False,
        "broker_order_object_allowed": False,
        "manual_reconciliation_required": True,
    }


def _validate_reservation(reservation):
    if not isinstance(reservation, dict):
        return None
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
        or reservation.get("broker_order_object_allowed") is not False
    ):
        return None
    authorization_id = _uuid4(reservation.get("authorization_id"))
    idempotency_key = reservation.get("idempotency_key")
    contract_sha256 = reservation.get("contract_sha256")
    receipt_sha256 = reservation.get("reservation_receipt_sha256")
    reserved_at = _utc_datetime(reservation.get("reserved_at"))
    if (
        authorization_id is None
        or not isinstance(idempotency_key, str)
        or not idempotency_key.strip()
        or not _valid_sha256(contract_sha256)
        or not _valid_sha256(receipt_sha256)
        or reserved_at is None
    ):
        return None
    return {
        "authorization_id": authorization_id,
        "idempotency_key": idempotency_key,
        "contract_sha256": contract_sha256,
        "reservation_receipt_sha256": receipt_sha256,
        "reserved_at": reserved_at,
    }


def _validate_attempt(attempt, reservation):
    if attempt is None:
        return {"present": False}
    if not isinstance(attempt, dict):
        return None
    if (
        attempt.get("status") != "SUBMISSION_ATTEMPT_RECORDED"
        or attempt.get("mode") != "PAPER"
        or attempt.get("automatic_retry_allowed") is not False
        or attempt.get("live_execution_allowed") is not False
    ):
        return None
    attempt_id = _uuid4(attempt.get("attempt_id"))
    attempted_at = _utc_datetime(attempt.get("attempted_at"))
    if attempt_id is None or attempted_at is None:
        return None
    for field in (
        "authorization_id",
        "idempotency_key",
        "contract_sha256",
        "reservation_receipt_sha256",
    ):
        if not hmac.compare_digest(
            str(attempt.get(field) or ""),
            str(reservation.get(field) or ""),
        ):
            return None

    request_dispatched = attempt.get("request_dispatched")
    local_failure_before_dispatch = attempt.get("local_failure_before_dispatch")
    if type(request_dispatched) is not bool or type(local_failure_before_dispatch) is not bool:
        return None
    if request_dispatched and local_failure_before_dispatch:
        return None

    expected = attempt.get("expected_order")
    if not isinstance(expected, dict):
        return None
    symbol = expected.get("symbol")
    side = expected.get("side")
    quantity = expected.get("quantity")
    limit_price = expected.get("limit_price")
    if (
        not _valid_symbol(symbol)
        or side not in ("BUY", "SELL")
        or type(quantity) is not int
        or quantity <= 0
        or not _positive_number(limit_price)
    ):
        return None

    client_id = attempt.get("client_id")
    order_id = attempt.get("order_id")
    if client_id is not None and (type(client_id) is not int or client_id < 0):
        return None
    if order_id is not None and (type(order_id) is not int or order_id < 0):
        return None

    return {
        "present": True,
        "attempt_id": attempt_id,
        "attempted_at": attempted_at,
        "request_dispatched": request_dispatched,
        "local_failure_before_dispatch": local_failure_before_dispatch,
        "expected_order": {
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "limit_price": float(limit_price),
        },
        "client_id": client_id,
        "order_id": order_id,
    }


def _validate_observation(observation, attempt, now, max_age_seconds):
    if observation is None:
        return {"present": False}
    if not isinstance(observation, dict):
        return None
    generated_at = _utc_datetime(observation.get("snapshot_generated_at_utc"))
    age = None if generated_at is None else (now - generated_at).total_seconds()
    if (
        observation.get("status") != "BROKER_OBSERVATION_READ_ONLY"
        or observation.get("mode") != "PAPER"
        or observation.get("broker_read_only") is not True
        or observation.get("live_trading_allowed") is not False
        or observation.get("order_submission_hard_blocked") is not True
        or observation.get("snapshot_verified") is not True
        or generated_at is None
        or age < 0
        or age > float(max_age_seconds)
        or not _valid_token(observation.get("paper_account_evidence_token"))
    ):
        return None

    observed = observation.get("order_observed")
    if type(observed) is not bool:
        return None
    if observed is False:
        if observation.get("order") not in (None, {}):
            return None
        return {
            "present": True,
            "order_observed": False,
            "snapshot_age_seconds": age,
        }

    order = observation.get("order")
    if not isinstance(order, dict):
        return None
    perm_id = order.get("perm_id")
    client_id = order.get("client_id")
    order_id = order.get("order_id")
    symbol = order.get("symbol")
    side = order.get("side")
    total = order.get("total_quantity")
    limit_price = order.get("limit_price")
    status = order.get("broker_status")
    filled = order.get("filled_quantity")
    remaining = order.get("remaining_quantity")
    execution_ids = order.get("execution_ids")

    if (
        type(perm_id) is not int
        or perm_id <= 0
        or type(client_id) is not int
        or client_id < 0
        or type(order_id) is not int
        or order_id < 0
        or not _valid_symbol(symbol)
        or side not in ("BUY", "SELL")
        or type(total) is not int
        or total <= 0
        or not _positive_number(limit_price)
        or not isinstance(status, str)
        or not _nonnegative_number(filled)
        or not _nonnegative_number(remaining)
        or filled > total
        or remaining > total
        or not isinstance(execution_ids, list)
        or not all(isinstance(x, str) and x.strip() for x in execution_ids)
        or len(execution_ids) != len(set(execution_ids))
    ):
        return None

    expected = attempt["expected_order"]
    if (
        symbol != expected["symbol"]
        or side != expected["side"]
        or total != expected["quantity"]
        or not math.isclose(
            float(limit_price),
            expected["limit_price"],
            rel_tol=1e-12,
            abs_tol=1e-7,
        )
    ):
        return None
    if attempt.get("client_id") is not None and client_id != attempt["client_id"]:
        return None
    if attempt.get("order_id") is not None and order_id != attempt["order_id"]:
        return None

    return {
        "present": True,
        "order_observed": True,
        "snapshot_age_seconds": age,
        "perm_id": perm_id,
        "client_id": client_id,
        "order_id": order_id,
        "broker_status": status,
        "filled_quantity": float(filled),
        "remaining_quantity": float(remaining),
        "total_quantity": total,
        "execution_count": len(execution_ids),
    }


def _classify_observed(observed):
    status = observed["broker_status"]
    filled = observed["filled_quantity"]
    remaining = observed["remaining_quantity"]
    total = float(observed["total_quantity"])

    if status not in SUPPORTED_BROKER_STATUSES:
        return "BROKER_STATUS_UNKNOWN_MANUAL_REVIEW", "UNSUPPORTED_BROKER_STATUS"

    if status == "Filled":
        if not math.isclose(filled, total, abs_tol=1e-7) or remaining > 1e-7:
            return None, "CONFLICTING_FILLED_QUANTITIES"
        return "BROKER_ORDER_FILLED", "BROKER_TERMINAL_FILL_OBSERVED"

    if status == "Cancelled":
        if filled >= total - 1e-7:
            return None, "CONFLICTING_CANCELLED_QUANTITIES"
        if filled > 0:
            return "BROKER_ORDER_PARTIALLY_FILLED_CANCELLED", "BROKER_CANCEL_AFTER_PARTIAL_FILL"
        return "BROKER_ORDER_CANCELLED_UNFILLED", "BROKER_CANCEL_CONFIRMED"

    if status == "Inactive":
        if filled > 0:
            return None, "CONFLICTING_INACTIVE_QUANTITIES"
        return "BROKER_ORDER_INACTIVE_MANUAL_REVIEW", "BROKER_INACTIVE_OBSERVED"

    if status in CANCEL_PENDING_STATUSES:
        return "BROKER_CANCEL_PENDING", "CANCELLATION_NOT_FINAL_DO_NOT_RETRY"

    if status in PENDING_STATUSES:
        return "BROKER_SUBMISSION_PENDING", "DESTINATION_ACCEPTANCE_UNCONFIRMED"

    if status in ACTIVE_STATUSES:
        if filled >= total - 1e-7 and remaining <= 1e-7:
            return None, "STATUS_LAGS_FULL_FILL_MANUAL_REVIEW"
        if filled > 0:
            return "BROKER_ORDER_PARTIALLY_FILLED_WORKING", "PARTIAL_FILL_ORDER_STILL_ACTIVE"
        return "BROKER_ORDER_OPEN_WORKING", "BROKER_ACTIVE_ORDER_OBSERVED"

    if status in MANUAL_REVIEW_STATUSES:
        return "BROKER_WARNING_MANUAL_REVIEW", "BROKER_WARNING_STATE_OBSERVED"

    return "BROKER_STATUS_UNKNOWN_MANUAL_REVIEW", "UNSUPPORTED_BROKER_STATUS"


def reconcile_submission_attempt(
    reservation,
    attempt=None,
    broker_observation=None,
    now=None,
    max_observation_age_seconds=DEFAULT_MAX_OBSERVATION_AGE_SECONDS,
):
    current = _utc_datetime(now)
    if now is not None and current is None:
        return {**_base(), "reason": "INVALID_EVALUATION_TIME"}
    current = current or datetime.now(timezone.utc)

    reservation_state = _validate_reservation(reservation)
    if reservation_state is None:
        return {**_base(), "reason": "INVALID_RESERVATION"}

    attempt_state = _validate_attempt(attempt, reservation_state)
    if attempt_state is None:
        return {**_base(), "reason": "INVALID_ATTEMPT_ARTIFACT"}

    if attempt_state["present"] is False:
        return {
            **_base(
                "RESERVED_NO_SUBMISSION_ATTEMPT",
                "AUTHORIZATION_RESERVED_BUT_NO_ATTEMPT_EVIDENCE",
            ),
            "authorization_id": reservation_state["authorization_id"],
            "manual_reconciliation_required": False,
            "next_action": "MANUAL_DECISION_REQUIRED_BEFORE_ANY_NEW_AUTHORIZATION",
        }

    if attempt_state["local_failure_before_dispatch"]:
        if broker_observation is not None:
            return {**_base(), "reason": "BROKER_OBSERVATION_CONFLICTS_WITH_LOCAL_PRE_DISPATCH_FAILURE"}
        return {
            **_base(
                "LOCAL_FAILURE_BEFORE_BROKER_DISPATCH",
                "NO_BROKER_SIDE_EFFECT_RECORDED",
            ),
            "authorization_id": reservation_state["authorization_id"],
            "attempt_id": attempt_state["attempt_id"],
            "manual_reconciliation_required": False,
            "next_action": "NEW_HUMAN_AUTHORIZATION_REQUIRED_FOR_ANY_RETRY",
        }

    if not attempt_state["request_dispatched"]:
        return {**_base(), "reason": "ATTEMPT_STATE_CONTRADICTORY"}

    observed = _validate_observation(
        broker_observation,
        attempt_state,
        current,
        max_observation_age_seconds,
    )
    if observed is None:
        return {**_base(), "reason": "INVALID_OR_STALE_BROKER_OBSERVATION"}

    if observed["present"] is False or observed["order_observed"] is False:
        return {
            **_base(
                "BROKER_OUTCOME_UNKNOWN_DO_NOT_RETRY",
                "DISPATCH_RECORDED_WITHOUT_MATCHING_BROKER_ORDER_EVIDENCE",
            ),
            "authorization_id": reservation_state["authorization_id"],
            "attempt_id": attempt_state["attempt_id"],
            "next_action": "REFRESH_READ_ONLY_BROKER_EVIDENCE_AND_MANUALLY_RECONCILE",
        }

    state, reason = _classify_observed(observed)
    if state is None:
        return {
            **_base("BLOCKED", reason),
            "authorization_id": reservation_state["authorization_id"],
            "attempt_id": attempt_state["attempt_id"],
            "perm_id": observed["perm_id"],
        }

    terminal = state in {
        "BROKER_ORDER_FILLED",
        "BROKER_ORDER_PARTIALLY_FILLED_CANCELLED",
        "BROKER_ORDER_CANCELLED_UNFILLED",
    }

    return {
        **_base(state, reason),
        "authorization_id": reservation_state["authorization_id"],
        "attempt_id": attempt_state["attempt_id"],
        "perm_id": observed["perm_id"],
        "client_id": observed["client_id"],
        "order_id": observed["order_id"],
        "broker_status": observed["broker_status"],
        "filled_quantity": observed["filled_quantity"],
        "remaining_quantity": observed["remaining_quantity"],
        "snapshot_age_seconds": observed["snapshot_age_seconds"],
        "terminal_broker_state_observed": terminal,
        "next_action": (
            "NO_RETRY_FINALIZE_AUDIT"
            if terminal
            else "REFRESH_READ_ONLY_BROKER_EVIDENCE_AND_MANUALLY_RECONCILE"
        ),
    }
