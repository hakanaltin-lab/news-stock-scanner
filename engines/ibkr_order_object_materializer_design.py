"""G8.25 non-executable IBKR Order-object materializer design gate."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import re
from uuid import UUID

from engines.offline_order_request_materializer_attestation import (
    ENGINE_VERSION as MATERIALIZER_ATTESTATION_ENGINE_VERSION,
    NEXT_GATE as MATERIALIZER_ATTESTATION_NEXT_GATE,
)
from engines.paper_adapter_implementation_candidate_review import PERMISSION_FLAGS


ENGINE_VERSION = "AURORA G8.25 IBKR Order Object Materializer Design Gate"
DESIGN_ID = "AURORA_G8_25_IBKR_ORDER_OBJECT_MATERIALIZER_DESIGN_V1"
DESIGN_NEXT_GATE = (
    "INDEPENDENT_IBKR_ORDER_OBJECT_MATERIALIZER_DESIGN_ATTESTATION_REQUIRED"
)

DESIGN_FIELDS = {
    "schema_version",
    "design_id",
    "design_status",
    "materializer_attestation_required",
    "materializer_attestation_next_gate",
    "target_api",
    "broker_mode",
    "host",
    "port",
    "asset_type",
    "accepted_request_schema_version",
    "accepted_order_type",
    "accepted_time_in_force",
    "contract_class",
    "order_class",
    "planned_contract_mapping",
    "planned_order_mapping",
    "transmit_must_be_false",
    "outside_rth_allowed",
    "market_order_allowed",
    "short_selling_allowed",
    "fractional_quantity_allowed",
    "raw_account_id_allowed",
    "credentials_allowed",
    "ibkr_import_allowed",
    "network_allowed",
    "order_id_allocation_allowed",
    "contract_resolution_allowed",
    *PERMISSION_FLAGS,
    "requires_independent_design_review",
    "signed_design_attestation_required",
    "next_gate",
}

ATTESTATION_FIELDS = {
    "engine",
    "status",
    "verified",
    "offline_materializer_independently_attested",
    "reason",
    "checks",
    "materializer_review_id",
    "reviewer_id",
    "captured_at_utc",
    "expires_at_utc",
    "review_request_sha256",
    "design_sha256",
    "materializer_source_sha256",
    "cli_source_sha256",
    "materializer_attestation_sha256",
    "reviewer_evidence_sha256",
    *PERMISSION_FLAGS,
    "next_gate",
}

EXPECTED_CONTRACT_MAPPING = {
    "symbol": "request.symbol",
    "secType": "STK",
    "exchange": "SMART",
    "currency": "USD",
}
EXPECTED_ORDER_MAPPING = {
    "action": "request.side",
    "totalQuantity": "request.quantity",
    "orderType": "LMT",
    "lmtPrice": "request.limit_price",
    "tif": "DAY",
    "outsideRth": False,
    "transmit": False,
}

_HEX_64 = re.compile(r"^[0-9a-f]{64}$")


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
    return text if _HEX_64.fullmatch(text) else None


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
            name in payload and payload.get(name) is False
            for name in PERMISSION_FLAGS
        )
    )


def _blocked(reason):
    return {
        "engine": ENGINE_VERSION,
        "status": "BLOCKED",
        "reason": reason,
        "design_validated": False,
        "materializer_attestation_verified": False,
        "materializer_review_id": None,
        "materializer_attestation_sha256": None,
        "offline_design_sha256": None,
        "materializer_source_sha256": None,
        "cli_source_sha256": None,
        "design_sha256": None,
        "independent_design_review_required": True,
        "signed_design_attestation_required": True,
        **{name: False for name in PERMISSION_FLAGS},
        "next_gate": "REPAIR_NON_EXECUTABLE_IBKR_ORDER_OBJECT_DESIGN",
    }


def evaluate_ibkr_order_object_design(
    design,
    materializer_attestation,
    *,
    now=None,
):
    now = (
        now.astimezone(timezone.utc)
        if isinstance(now, datetime) and now.tzinfo is not None
        else datetime.now(timezone.utc)
    )

    if not isinstance(design, dict):
        return _blocked("DESIGN_ARTIFACT_INVALID")
    if not isinstance(materializer_attestation, dict):
        return _blocked("MATERIALIZER_ATTESTATION_RESULT_INVALID")
    if set(design) != DESIGN_FIELDS:
        return _blocked("DESIGN_FIELD_SET_INVALID")
    if set(materializer_attestation) != ATTESTATION_FIELDS:
        return _blocked("MATERIALIZER_ATTESTATION_FIELD_SET_INVALID")

    checks = materializer_attestation.get("checks")
    attestation_verified = (
        materializer_attestation.get("engine")
        == MATERIALIZER_ATTESTATION_ENGINE_VERSION
        and materializer_attestation.get("status") == "VERIFIED"
        and materializer_attestation.get("verified") is True
        and materializer_attestation.get(
            "offline_materializer_independently_attested"
        )
        is True
        and materializer_attestation.get("reason")
        == "INDEPENDENT_OFFLINE_MATERIALIZER_ATTESTATION_VERIFIED"
        and isinstance(checks, dict)
        and bool(checks)
        and all(value is True for value in checks.values())
        and _permissions_false(materializer_attestation)
        and materializer_attestation.get("next_gate")
        == MATERIALIZER_ATTESTATION_NEXT_GATE
    )
    if not attestation_verified:
        return _blocked("MATERIALIZER_ATTESTATION_NOT_VERIFIED")

    captured = _utc_datetime(materializer_attestation.get("captured_at_utc"))
    expires = _utc_datetime(materializer_attestation.get("expires_at_utc"))
    if (
        captured is None
        or expires is None
        or not captured <= now <= expires
    ):
        return _blocked("MATERIALIZER_ATTESTATION_NOT_CURRENT")

    materializer_review_id = _uuid4(
        materializer_attestation.get("materializer_review_id")
    )
    materializer_attestation_sha256 = _sha256(
        materializer_attestation.get("materializer_attestation_sha256")
    )
    offline_design_sha256 = _sha256(
        materializer_attestation.get("design_sha256")
    )
    materializer_source_sha256 = _sha256(
        materializer_attestation.get("materializer_source_sha256")
    )
    cli_source_sha256 = _sha256(
        materializer_attestation.get("cli_source_sha256")
    )
    supporting = (
        _sha256(materializer_attestation.get("review_request_sha256")),
        _sha256(materializer_attestation.get("reviewer_evidence_sha256")),
    )
    if (
        materializer_review_id is None
        or materializer_attestation_sha256 is None
        or offline_design_sha256 is None
        or materializer_source_sha256 is None
        or cli_source_sha256 is None
        or any(value is None for value in supporting)
    ):
        return _blocked("MATERIALIZER_ATTESTATION_BINDING_INVALID")

    design_safe = (
        design.get("schema_version") == 1
        and design.get("design_id") == DESIGN_ID
        and design.get("design_status") == "REVIEW_REQUIRED"
        and design.get("materializer_attestation_required") is True
        and design.get("materializer_attestation_next_gate")
        == MATERIALIZER_ATTESTATION_NEXT_GATE
        and design.get("target_api") == "IBKR_TWS_API"
        and design.get("broker_mode") == "PAPER"
        and design.get("host") == "127.0.0.1"
        and design.get("port") == 4002
        and design.get("asset_type") == "STK"
        and design.get("accepted_request_schema_version") == 1
        and design.get("accepted_order_type") == "LMT"
        and design.get("accepted_time_in_force") == "DAY"
        and design.get("contract_class") == "ibapi.contract.Contract"
        and design.get("order_class") == "ibapi.order.Order"
        and design.get("planned_contract_mapping")
        == EXPECTED_CONTRACT_MAPPING
        and design.get("planned_order_mapping")
        == EXPECTED_ORDER_MAPPING
        and design.get("transmit_must_be_false") is True
        and design.get("outside_rth_allowed") is False
        and design.get("market_order_allowed") is False
        and design.get("short_selling_allowed") is False
        and design.get("fractional_quantity_allowed") is False
        and design.get("raw_account_id_allowed") is False
        and design.get("credentials_allowed") is False
        and design.get("ibkr_import_allowed") is False
        and design.get("network_allowed") is False
        and design.get("order_id_allocation_allowed") is False
        and design.get("contract_resolution_allowed") is False
        and _permissions_false(design)
        and design.get("requires_independent_design_review") is True
        and design.get("signed_design_attestation_required") is True
        and design.get("next_gate") == DESIGN_NEXT_GATE
    )
    if not design_safe:
        return _blocked("IBKR_ORDER_OBJECT_DESIGN_POLICY_INVALID")

    design_sha256 = canonical_json_sha256(design)
    if design_sha256 is None:
        return _blocked("IBKR_ORDER_OBJECT_DESIGN_DIGEST_UNAVAILABLE")

    return {
        "engine": ENGINE_VERSION,
        "status": "DESIGN_VALIDATED_NON_EXECUTABLE",
        "reason": "INDEPENDENT_IBKR_ORDER_OBJECT_DESIGN_REVIEW_REQUIRED",
        "design_validated": True,
        "materializer_attestation_verified": True,
        "materializer_review_id": materializer_review_id,
        "materializer_attestation_sha256": materializer_attestation_sha256,
        "offline_design_sha256": offline_design_sha256,
        "materializer_source_sha256": materializer_source_sha256,
        "cli_source_sha256": cli_source_sha256,
        "design_sha256": design_sha256,
        "independent_design_review_required": True,
        "signed_design_attestation_required": True,
        **{name: False for name in PERMISSION_FLAGS},
        "next_gate": DESIGN_NEXT_GATE,
    }
