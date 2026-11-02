"""G8.22 pure offline order-request preview materializer.

This module creates a normalized internal preview only. It does not import
IBKR, open a network connection, create a broker request/order object, or
submit/cancel/modify an order.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import json
import re
from uuid import UUID

from engines.paper_adapter_implementation_candidate_attestation import (
    ENGINE_VERSION as CANDIDATE_ATTESTATION_ENGINE_VERSION,
)
from engines.paper_adapter_implementation_candidate_review import (
    PERMISSION_FLAGS,
)


ENGINE_VERSION = "AURORA G8.22 Offline Order Request Materializer"
DESIGN_ID = "AURORA_G8_22_OFFLINE_ORDER_REQUEST_MATERIALIZER_DESIGN_V1"
NEXT_GATE = "INDEPENDENT_OFFLINE_ORDER_REQUEST_MATERIALIZER_REVIEW_REQUIRED"

DESIGN_FIELDS = {
    "schema_version",
    "design_id",
    "candidate_attestation_required",
    "candidate_attestation_next_gate",
    "accepted_order_type",
    "accepted_time_in_force",
    "accepted_sides",
    "symbol_pattern",
    "quantity_min",
    "quantity_max",
    "limit_price_scale_max",
    "outside_rth_allowed",
    "fractional_quantity_allowed",
    "market_order_allowed",
    "sell_requires_reduce_only",
    "sell_requires_position_coverage",
    "raw_account_id_allowed",
    "credentials_allowed",
    "ibkr_import_allowed",
    "network_allowed",
    *PERMISSION_FLAGS,
    "next_gate",
}

CANDIDATE_ATTESTATION_FIELDS = {
    "engine",
    "status",
    "verified",
    "adapter_candidate_independently_attested",
    "reason",
    "checks",
    "candidate_review_id",
    "reviewer_id",
    "captured_at_utc",
    "expires_at_utc",
    "candidate_review_artifact_sha256",
    "review_request_sha256",
    "candidate_source_sha256",
    "candidate_attestation_sha256",
    "design_attestation_sha256",
    "design_sha256",
    "design_review_id",
    "source_attestation_sha256",
    "source_git_sha",
    "reviewer_evidence_sha256",
    *PERMISSION_FLAGS,
    "next_gate",
}

INTENT_FIELDS = {
    "intent_id",
    "symbol",
    "side",
    "quantity",
    "position_quantity",
    "limit_price",
    "order_type",
    "time_in_force",
    "outside_rth",
    "reduce_only",
}

_SYMBOL = re.compile(r"^[A-Z][A-Z0-9.-]{0,11}$")
_PRICE = re.compile(r"^[0-9]{1,8}(?:\.[0-9]{1,4})?$")


def canonical_json_sha256(payload):
    if not isinstance(payload, dict):
        return None
    try:
        raw = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, OverflowError):
        return None
    return hashlib.sha256(raw).hexdigest()


def _sha256(value):
    text = str(value or "").strip().lower()
    if (
        len(text) != 64
        or any(
            ch not in "0123456789abcdef"
            for ch in text
        )
    ):
        return None
    return text


def _uuid4(value):
    text = str(value or "").strip()
    try:
        parsed = UUID(text)
    except (ValueError, AttributeError):
        return None
    return text if parsed.version == 4 and str(parsed) == text else None


def _utc_datetime(value):
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


def _permissions_false(payload):
    return (
        isinstance(payload, dict)
        and all(
            name in payload
            and payload.get(name) is False
            for name in PERMISSION_FLAGS
        )
    )


def _blocked(reason):
    return {
        "engine": ENGINE_VERSION,
        "status": "BLOCKED",
        "reason": reason,
        "offline_request_materialized": False,
        "candidate_attestation_verified": False,
        "request": None,
        "request_sha256": None,
        "design_sha256": None,
        "candidate_attestation_sha256": None,
        "broker_request_materialized": False,
        "broker_order_object_created": False,
        "network_accessed": False,
        "transmit": False,
        **{
            name: False
            for name in PERMISSION_FLAGS
        },
        "next_gate": "REPAIR_OFFLINE_ORDER_REQUEST_INPUT",
    }


def _validate_design(design):
    return (
        isinstance(design, dict)
        and set(design) == DESIGN_FIELDS
        and design.get("schema_version") == 1
        and design.get("design_id") == DESIGN_ID
        and design.get("candidate_attestation_required") is True
        and design.get("candidate_attestation_next_gate")
        == "OFFLINE_ORDER_REQUEST_MATERIALIZER_DESIGN_REQUIRED"
        and design.get("accepted_order_type") == "LMT"
        and design.get("accepted_time_in_force") == "DAY"
        and design.get("accepted_sides") == ["BUY", "SELL"]
        and design.get("symbol_pattern") == _SYMBOL.pattern
        and design.get("quantity_min") == 1
        and design.get("quantity_max") == 100000
        and design.get("limit_price_scale_max") == 4
        and design.get("outside_rth_allowed") is False
        and design.get("fractional_quantity_allowed") is False
        and design.get("market_order_allowed") is False
        and design.get("sell_requires_reduce_only") is True
        and design.get("sell_requires_position_coverage") is True
        and design.get("raw_account_id_allowed") is False
        and design.get("credentials_allowed") is False
        and design.get("ibkr_import_allowed") is False
        and design.get("network_allowed") is False
        and _permissions_false(design)
        and design.get("next_gate") == NEXT_GATE
    )


def _validate_candidate_attestation(attestation, now):
    if (
        not isinstance(attestation, dict)
        or set(attestation) != CANDIDATE_ATTESTATION_FIELDS
    ):
        return None

    checks = attestation.get("checks")
    captured = _utc_datetime(
        attestation.get("captured_at_utc")
    )
    expires = _utc_datetime(
        attestation.get("expires_at_utc")
    )

    safe = (
        attestation.get("engine")
        == CANDIDATE_ATTESTATION_ENGINE_VERSION
        and attestation.get("status") == "VERIFIED"
        and attestation.get("verified") is True
        and attestation.get(
            "adapter_candidate_independently_attested"
        )
        is True
        and attestation.get("reason")
        == "INDEPENDENT_IMPLEMENTATION_CANDIDATE_ATTESTATION_VERIFIED"
        and isinstance(checks, dict)
        and bool(checks)
        and all(value is True for value in checks.values())
        and _permissions_false(attestation)
        and attestation.get("next_gate")
        == "OFFLINE_ORDER_REQUEST_MATERIALIZER_DESIGN_REQUIRED"
        and captured is not None
        and expires is not None
        and captured <= now <= expires
        and _uuid4(attestation.get("candidate_review_id"))
        is not None
        and _sha256(
            attestation.get("candidate_source_sha256")
        )
        is not None
        and _sha256(
            attestation.get("candidate_attestation_sha256")
        )
        is not None
        and _sha256(
            attestation.get("design_attestation_sha256")
        )
        is not None
        and _sha256(attestation.get("design_sha256"))
        is not None
    )
    return attestation if safe else None


def _normalize_price(value):
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not _PRICE.fullmatch(text):
        return None
    try:
        price = Decimal(text)
    except InvalidOperation:
        return None
    if not price.is_finite() or price <= 0:
        return None
    normalized = format(price.normalize(), "f")
    if "." in normalized:
        normalized = normalized.rstrip("0").rstrip(".")
    return normalized


def materialize_offline_order_request(
    design,
    candidate_attestation,
    intent,
    *,
    now=None,
):
    now = (
        now.astimezone(timezone.utc)
        if isinstance(now, datetime)
        and now.tzinfo is not None
        else datetime.now(timezone.utc)
    )

    if not _validate_design(design):
        return _blocked("MATERIALIZER_DESIGN_INVALID")

    attestation = _validate_candidate_attestation(
        candidate_attestation,
        now,
    )
    if attestation is None:
        return _blocked(
            "CANDIDATE_ATTESTATION_NOT_VERIFIED"
        )

    if (
        not isinstance(intent, dict)
        or set(intent) != INTENT_FIELDS
    ):
        return _blocked("ORDER_INTENT_FIELD_SET_INVALID")

    intent_id = _uuid4(intent.get("intent_id"))
    symbol = str(intent.get("symbol") or "")
    side = str(intent.get("side") or "")
    quantity = intent.get("quantity")
    position_quantity = intent.get("position_quantity")
    price = _normalize_price(
        intent.get("limit_price")
    )

    common_valid = (
        intent_id is not None
        and bool(_SYMBOL.fullmatch(symbol))
        and side in {"BUY", "SELL"}
        and type(quantity) is int
        and 1 <= quantity <= 100000
        and type(position_quantity) is int
        and position_quantity >= 0
        and price is not None
        and intent.get("order_type") == "LMT"
        and intent.get("time_in_force") == "DAY"
        and intent.get("outside_rth") is False
        and type(intent.get("reduce_only")) is bool
    )
    if not common_valid:
        return _blocked("ORDER_INTENT_INVALID")

    if side == "SELL":
        if (
            intent.get("reduce_only") is not True
            or position_quantity < quantity
        ):
            return _blocked(
                "SELL_REDUCE_ONLY_POSITION_COVERAGE_REQUIRED"
            )
    elif intent.get("reduce_only") is not False:
        return _blocked(
            "BUY_REDUCE_ONLY_MUST_BE_FALSE"
        )

    candidate_attestation_sha256 = _sha256(
        attestation.get(
            "candidate_attestation_sha256"
        )
    )
    if candidate_attestation_sha256 is None:
        return _blocked(
            "CANDIDATE_ATTESTATION_BINDING_INVALID"
        )

    request = {
        "request_schema_version": 1,
        "intent_id": intent_id,
        "symbol": symbol,
        "side": side,
        "quantity": quantity,
        "position_quantity_at_validation": (
            position_quantity
        ),
        "limit_price": price,
        "order_type": "LMT",
        "time_in_force": "DAY",
        "outside_rth": False,
        "reduce_only": intent.get("reduce_only"),
        "paper_only": True,
        "transmit": False,
        "broker_request_materialized": False,
        "broker_order_object_created": False,
        "candidate_attestation_sha256": (
            candidate_attestation_sha256
        ),
    }
    request_sha256 = canonical_json_sha256(
        request
    )
    design_sha256 = canonical_json_sha256(
        design
    )
    if (
        request_sha256 is None
        or design_sha256 is None
    ):
        return _blocked(
            "OFFLINE_REQUEST_DIGEST_UNAVAILABLE"
        )

    return {
        "engine": ENGINE_VERSION,
        "status": "OFFLINE_ORDER_REQUEST_PREVIEW_READY",
        "reason": "OFFLINE_PREVIEW_ONLY_NO_BROKER_OBJECT",
        "offline_request_materialized": True,
        "candidate_attestation_verified": True,
        "request": request,
        "request_sha256": request_sha256,
        "design_sha256": design_sha256,
        "candidate_attestation_sha256": (
            candidate_attestation_sha256
        ),
        "broker_request_materialized": False,
        "broker_order_object_created": False,
        "network_accessed": False,
        "transmit": False,
        **{
            name: False
            for name in PERMISSION_FLAGS
        },
        "next_gate": NEXT_GATE,
    }
