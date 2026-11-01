"""G6.19 broker-neutral Paper adapter implementation review contract.

This module freezes the safety specification a future IBKR Paper adapter must
satisfy. It validates a G6.18 review envelope and a declarative implementation
manifest. It does not import a broker API, construct an order object, connect,
submit, cancel, modify, or retry an order.
"""

from datetime import datetime, timezone
import hashlib
import json
import math
from uuid import UUID

from engines.paper_adapter_review_envelope import ENVELOPE_VERSION
from engines.paper_submission_attempt_journal import JOURNAL_VERSION


CONTRACT_VERSION = "AURORA_G6_19_ADAPTER_IMPLEMENTATION_REVIEW_V1"
MANIFEST_VERSION = "AURORA_G6_19_ADAPTER_MANIFEST_V1"
DEFAULT_MAX_ENVELOPE_AGE_SECONDS = 30

REQUIRED_MANIFEST_FIELDS = frozenset((
    "version",
    "broker",
    "api_family",
    "mode",
    "host",
    "port",
    "client_id",
    "asset_type",
    "order_type",
    "time_in_force",
    "fractional_shares_supported",
    "short_selling_supported",
    "market_orders_supported",
    "automatic_retry_supported",
    "automatic_cancel_supported",
    "automatic_modify_supported",
    "live_mode_supported",
    "live_port_allowed",
    "credentials_in_repository_allowed",
    "raw_account_id_in_artifacts_allowed",
    "order_submission_implemented",
    "broker_order_object_implemented",
    "broker_request_materialization_implemented",
    "source_review_required",
    "real_paper_readonly_evidence_required",
    "independent_security_review_required",
    "explicit_paper_execution_release_required",
    "explicit_live_execution_release_required",
))


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


def _valid_token(value):
    return (
        isinstance(value, str)
        and value.startswith("IBKR-EVID-")
        and len(value) == 26
        and all(c in "0123456789ABCDEF" for c in value[10:])
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


def _safe_base(status="BLOCKED", reason="IMPLEMENTATION_REVIEW_BLOCKED"):
    return {
        "engine": "AURORA G6.19 Paper Adapter Implementation Review Contract",
        "contract_version": CONTRACT_VERSION,
        "status": status,
        "reason": reason,
        "implementation_allowed": False,
        "connection_allowed": False,
        "broker_submission_allowed": False,
        "paper_order_submission_allowed": False,
        "live_execution_allowed": False,
        "automatic_retry_allowed": False,
        "automatic_cancel_allowed": False,
        "automatic_modify_allowed": False,
        "broker_order_object_allowed": False,
        "broker_request_materialization_allowed": False,
    }


def _envelope_payload(envelope):
    return {
        "version": envelope.get("version"),
        "generated_at": envelope.get("generated_at"),
        "attempt_journal_version": envelope.get("attempt_journal_version"),
        "attempt_id": envelope.get("attempt_id"),
        "authorization_id": envelope.get("authorization_id"),
        "idempotency_key": envelope.get("idempotency_key"),
        "contract_sha256": envelope.get("contract_sha256"),
        "reservation_receipt_sha256": envelope.get(
            "reservation_receipt_sha256"
        ),
        "intent_sha256": envelope.get("intent_sha256"),
        "expected_order_sha256": envelope.get("expected_order_sha256"),
        "paper_account_evidence_token": envelope.get(
            "paper_account_evidence_token"
        ),
        "order": envelope.get("order"),
        "constraints": envelope.get("constraints"),
    }


def _validate_envelope(envelope, current, max_age_seconds):
    if not isinstance(envelope, dict):
        return None, "INVALID_REVIEW_ENVELOPE"
    if (
        envelope.get("status")
        != "ADAPTER_REVIEW_ENVELOPE_VALIDATED_NON_EXECUTABLE"
        or envelope.get("reason")
        != "PREPARED_ATTEMPT_REVIEW_ENVELOPE_READY"
        or envelope.get("review_only") is not True
        or envelope.get("version") != ENVELOPE_VERSION
        or envelope.get("attempt_journal_version") != JOURNAL_VERSION
        or envelope.get("next_gate")
        != "IBKR_PAPER_ADAPTER_IMPLEMENTATION_REVIEW_REQUIRED"
    ):
        return None, "REVIEW_ENVELOPE_STATE_INVALID"

    for field in (
        "contract_sha256",
        "reservation_receipt_sha256",
        "intent_sha256",
        "expected_order_sha256",
        "review_envelope_sha256",
    ):
        if not _valid_sha256(envelope.get(field)):
            return None, "REVIEW_ENVELOPE_DIGEST_INVALID"

    if (
        _uuid4(envelope.get("attempt_id")) is None
        or _uuid4(envelope.get("authorization_id")) is None
        or not isinstance(envelope.get("idempotency_key"), str)
        or not envelope["idempotency_key"].strip()
        or not _valid_token(envelope.get("paper_account_evidence_token"))
    ):
        return None, "REVIEW_ENVELOPE_IDENTITY_INVALID"

    generated_at = _utc_datetime(envelope.get("generated_at"))
    if generated_at is None:
        return None, "REVIEW_ENVELOPE_TIME_INVALID"
    age = (current - generated_at).total_seconds()
    if age < 0 or age > float(max_age_seconds):
        return None, "REVIEW_ENVELOPE_STALE"

    constraints = envelope.get("constraints")
    if not isinstance(constraints, dict) or constraints != {
        "mode": "PAPER",
        "live_execution_allowed": False,
        "automatic_retry_allowed": False,
        "automatic_cancel_allowed": False,
        "automatic_modify_allowed": False,
        "broker_order_object_allowed": False,
        "broker_request_materialization_allowed": False,
    }:
        return None, "REVIEW_ENVELOPE_CONSTRAINTS_INVALID"

    order = envelope.get("order")
    if (
        not isinstance(order, dict)
        or set(order) != {
            "symbol",
            "side",
            "asset_type",
            "order_type",
            "time_in_force",
            "quantity",
            "limit_price",
        }
        or not _valid_symbol(order.get("symbol"))
        or order.get("side") not in ("BUY", "SELL")
        or order.get("asset_type") != "STK"
        or order.get("order_type") != "LMT"
        or order.get("time_in_force") != "DAY"
        or type(order.get("quantity")) is not int
        or order.get("quantity") <= 0
        or type(order.get("limit_price")) not in (int, float)
        or not math.isfinite(order.get("limit_price"))
        or order.get("limit_price") <= 0
    ):
        return None, "REVIEW_ENVELOPE_ORDER_INVALID"

    expected_order = {
        "symbol": order["symbol"],
        "side": order["side"],
        "quantity": order["quantity"],
        "limit_price": float(order["limit_price"]),
    }
    expected_order_sha256 = _digest(expected_order)
    if (
        expected_order_sha256 is None
        or expected_order_sha256 != envelope["expected_order_sha256"]
    ):
        return None, "EXPECTED_ORDER_DIGEST_MISMATCH"

    calculated_envelope_sha256 = _digest(_envelope_payload(envelope))
    if (
        calculated_envelope_sha256 is None
        or calculated_envelope_sha256
        != envelope["review_envelope_sha256"]
    ):
        return None, "REVIEW_ENVELOPE_DIGEST_MISMATCH"

    unsafe_flags = (
        "broker_submission_allowed",
        "paper_order_submission_allowed",
        "live_execution_allowed",
        "automatic_retry_allowed",
        "automatic_cancel_allowed",
        "automatic_modify_allowed",
        "broker_order_object_allowed",
        "broker_request_materialization_allowed",
    )
    if any(envelope.get(field) is not False for field in unsafe_flags):
        return None, "REVIEW_ENVELOPE_PERMISSION_INVALID"

    return {
        "generated_at": generated_at,
        "age_seconds": age,
        "order": order,
    }, None


def _validate_manifest(manifest):
    if not isinstance(manifest, dict):
        return None, "INVALID_IMPLEMENTATION_MANIFEST"
    if set(manifest) != REQUIRED_MANIFEST_FIELDS:
        return None, "IMPLEMENTATION_MANIFEST_SCHEMA_INVALID"

    client_id = manifest.get("client_id")
    if type(client_id) is not int or not (0 <= client_id <= 2147483647):
        return None, "IMPLEMENTATION_CLIENT_ID_INVALID"

    required_values = {
        "version": MANIFEST_VERSION,
        "broker": "IBKR",
        "api_family": "TWS_API",
        "mode": "PAPER",
        "host": "127.0.0.1",
        "port": 4002,
        "asset_type": "STK",
        "order_type": "LMT",
        "time_in_force": "DAY",
        "fractional_shares_supported": False,
        "short_selling_supported": False,
        "market_orders_supported": False,
        "automatic_retry_supported": False,
        "automatic_cancel_supported": False,
        "automatic_modify_supported": False,
        "live_mode_supported": False,
        "live_port_allowed": False,
        "credentials_in_repository_allowed": False,
        "raw_account_id_in_artifacts_allowed": False,
        "order_submission_implemented": False,
        "broker_order_object_implemented": False,
        "broker_request_materialization_implemented": False,
        "source_review_required": True,
        "real_paper_readonly_evidence_required": True,
        "independent_security_review_required": True,
        "explicit_paper_execution_release_required": True,
        "explicit_live_execution_release_required": True,
    }
    for field, expected in required_values.items():
        if manifest.get(field) != expected:
            return None, f"IMPLEMENTATION_MANIFEST_{field.upper()}_INVALID"

    digest = _digest(manifest)
    if digest is None:
        return None, "NON_CANONICAL_IMPLEMENTATION_MANIFEST"

    return {
        "client_id": client_id,
        "manifest_sha256": digest,
    }, None


def evaluate_adapter_implementation_review(
    review_envelope,
    implementation_manifest,
    now=None,
    max_envelope_age_seconds=DEFAULT_MAX_ENVELOPE_AGE_SECONDS,
):
    current = _utc_datetime(now)
    if now is not None and current is None:
        return {**_safe_base(), "reason": "INVALID_EVALUATION_TIME"}
    current = current or datetime.now(timezone.utc)

    envelope_state, envelope_error = _validate_envelope(
        review_envelope,
        current,
        max_envelope_age_seconds,
    )
    if envelope_error:
        return {**_safe_base(), "reason": envelope_error}

    manifest_state, manifest_error = _validate_manifest(
        implementation_manifest
    )
    if manifest_error:
        return {**_safe_base(), "reason": manifest_error}

    contract_payload = {
        "version": CONTRACT_VERSION,
        "generated_at": current.isoformat(),
        "review_envelope_sha256": review_envelope[
            "review_envelope_sha256"
        ],
        "implementation_manifest_sha256": manifest_state[
            "manifest_sha256"
        ],
        "attempt_id": review_envelope["attempt_id"],
        "authorization_id": review_envelope["authorization_id"],
        "idempotency_key": review_envelope["idempotency_key"],
        "paper_account_evidence_token": review_envelope[
            "paper_account_evidence_token"
        ],
        "client_id": manifest_state["client_id"],
        "order": envelope_state["order"],
        "release_prerequisites": {
            "g6_11_real_paper_readonly_evidence_required": True,
            "independent_source_review_required": True,
            "paper_execution_release_required": True,
            "live_execution_release_required": True,
        },
    }
    contract_sha256 = _digest(contract_payload)
    if contract_sha256 is None:
        return {**_safe_base(), "reason": "NON_CANONICAL_REVIEW_CONTRACT"}

    return {
        **_safe_base(
            "IMPLEMENTATION_REVIEW_CONTRACT_VALIDATED_NON_EXECUTABLE",
            "ADAPTER_SPECIFICATION_FROZEN_FOR_REVIEW",
        ),
        **contract_payload,
        "implementation_review_contract_sha256": contract_sha256,
        "review_envelope_age_seconds": envelope_state["age_seconds"],
        "next_gate": "G6_20_ADAPTER_SOURCE_POLICY_REVIEW_REQUIRED",
    }
