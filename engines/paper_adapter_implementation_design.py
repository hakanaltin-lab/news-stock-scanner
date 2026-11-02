"""G8.16 non-executable Paper adapter implementation-design gate.

This gate consumes a verified G8.15 source-attestation result and a fixed
tracked design contract. It never imports the adapter, opens a broker
connection, materializes an order request, or enables execution.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from uuid import UUID

from engines.paper_adapter_source_attestation import (
    ENGINE_VERSION as SOURCE_ATTESTATION_ENGINE_VERSION,
)
from engines.paper_adapter_source_review import (
    EXPECTED_CLASS,
    SKELETON_VERSION,
)


ENGINE_VERSION = "AURORA G8.16 Paper Adapter Implementation Design Gate"
DESIGN_ID = "AURORA_G8_16_IBKR_PAPER_ADAPTER_IMPLEMENTATION_DESIGN_V1"
DESIGN_NEXT_GATE = (
    "INDEPENDENT_ADAPTER_IMPLEMENTATION_DESIGN_ATTESTATION_REQUIRED"
)
SOURCE_NEXT_GATE = (
    "NON_EXECUTABLE_ADAPTER_IMPLEMENTATION_DESIGN_REVIEW_REQUIRED"
)

PERMISSION_FLAGS = (
    "implementation_allowed",
    "connection_allowed",
    "broker_request_materialization_allowed",
    "broker_order_object_allowed",
    "automatic_retry_allowed",
    "automatic_cancel_allowed",
    "automatic_modify_allowed",
    "broker_submission_allowed",
    "paper_order_submission_allowed",
    "live_execution_allowed",
    "automatic_promotion_allowed",
    "real_money_trading_allowed",
)

DESIGN_FIELDS = {
    "schema_version",
    "design_id",
    "design_status",
    "source_attestation_required",
    "source_attestation_next_gate",
    "skeleton_version",
    "adapter_class",
    "broker_mode",
    "host",
    "port",
    "asset_type",
    "order_type",
    "time_in_force",
    "planned_methods",
    "market_order_allowed",
    "short_selling_allowed",
    "fractional_quantity_allowed",
    "credentials_allowed",
    "raw_account_id_allowed",
    *PERMISSION_FLAGS,
    "requires_independent_design_review",
    "signed_design_attestation_required",
    "next_gate",
}

SOURCE_ATTESTATION_FIELDS = {
    "engine",
    "status",
    "verified",
    "adapter_source_independently_attested",
    "reason",
    "checks",
    "review_id",
    "reviewer_id",
    "captured_at_utc",
    "expires_at_utc",
    "git_sha",
    "source_review_artifact_sha256",
    "review_request_sha256",
    "source_sha256",
    "source_policy_sha256",
    "source_attestation_sha256",
    "reviewer_evidence_sha256",
    *PERMISSION_FLAGS,
    "next_gate",
}

EXPECTED_METHODS = [
    "connect",
    "materialize_order_request",
    "submit_order",
    "cancel_order",
    "modify_order",
]


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
            character not in "0123456789abcdef"
            for character in text
        )
    ):
        return None
    return text


def _git_sha(value):
    text = str(value or "").strip().lower()
    if (
        len(text) != 40
        or any(
            character not in "0123456789abcdef"
            for character in text
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
    return (
        text
        if parsed.version == 4
        and str(parsed) == text
        else None
    )


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
        "design_validated": False,
        "source_attestation_verified": False,
        "source_review_id": None,
        "source_git_sha": None,
        "source_sha256": None,
        "source_attestation_sha256": None,
        "design_sha256": None,
        "independent_design_review_required": True,
        "signed_design_attestation_required": True,
        **{
            name: False
            for name in PERMISSION_FLAGS
        },
        "next_gate": "REPAIR_NON_EXECUTABLE_IMPLEMENTATION_DESIGN",
    }


def evaluate_implementation_design(
    design,
    source_attestation,
    source_text,
    *,
    now=None,
):
    now = (
        now.astimezone(timezone.utc)
        if isinstance(now, datetime)
        and now.tzinfo is not None
        else datetime.now(timezone.utc)
    )

    if not isinstance(design, dict):
        return _blocked("DESIGN_ARTIFACT_INVALID")
    if not isinstance(source_attestation, dict):
        return _blocked("SOURCE_ATTESTATION_RESULT_INVALID")
    if not isinstance(source_text, str) or not source_text:
        return _blocked("TRACKED_SOURCE_UNAVAILABLE")

    if set(design) != DESIGN_FIELDS:
        return _blocked("DESIGN_FIELD_SET_INVALID")
    if set(source_attestation) != SOURCE_ATTESTATION_FIELDS:
        return _blocked("SOURCE_ATTESTATION_FIELD_SET_INVALID")

    checks = source_attestation.get("checks")
    source_verified = (
        source_attestation.get("engine")
        == SOURCE_ATTESTATION_ENGINE_VERSION
        and source_attestation.get("status") == "VERIFIED"
        and source_attestation.get("verified") is True
        and source_attestation.get(
            "adapter_source_independently_attested"
        ) is True
        and source_attestation.get("reason")
        == "INDEPENDENT_SOURCE_REVIEW_ATTESTATION_VERIFIED"
        and isinstance(checks, dict)
        and bool(checks)
        and all(
            value is True
            for value in checks.values()
        )
        and _permissions_false(source_attestation)
        and source_attestation.get("next_gate")
        == SOURCE_NEXT_GATE
    )
    if not source_verified:
        return _blocked("SOURCE_ATTESTATION_NOT_VERIFIED")

    captured = _utc_datetime(
        source_attestation.get("captured_at_utc")
    )
    expires = _utc_datetime(
        source_attestation.get("expires_at_utc")
    )
    if (
        captured is None
        or expires is None
        or not captured <= now <= expires
    ):
        return _blocked("SOURCE_ATTESTATION_NOT_CURRENT")

    review_id = _uuid4(
        source_attestation.get("review_id")
    )
    source_git_sha = _git_sha(
        source_attestation.get("git_sha")
    )
    attested_source_sha = _sha256(
        source_attestation.get("source_sha256")
    )
    source_attestation_sha = _sha256(
        source_attestation.get(
            "source_attestation_sha256"
        )
    )
    supporting_digests = (
        _sha256(
            source_attestation.get(
                "source_review_artifact_sha256"
            )
        ),
        _sha256(
            source_attestation.get(
                "review_request_sha256"
            )
        ),
        _sha256(
            source_attestation.get(
                "source_policy_sha256"
            )
        ),
        _sha256(
            source_attestation.get(
                "reviewer_evidence_sha256"
            )
        ),
    )
    if (
        review_id is None
        or source_git_sha is None
        or attested_source_sha is None
        or source_attestation_sha is None
        or any(
            value is None
            for value in supporting_digests
        )
    ):
        return _blocked("SOURCE_ATTESTATION_BINDING_INVALID")

    actual_source_sha = hashlib.sha256(
        source_text.encode("utf-8")
    ).hexdigest()
    if actual_source_sha != attested_source_sha:
        return _blocked("TRACKED_SOURCE_CHANGED_AFTER_ATTESTATION")

    design_safe = (
        design.get("schema_version") == 1
        and design.get("design_id") == DESIGN_ID
        and design.get("design_status") == "REVIEW_REQUIRED"
        and design.get("source_attestation_required") is True
        and design.get("source_attestation_next_gate")
        == SOURCE_NEXT_GATE
        and design.get("skeleton_version") == SKELETON_VERSION
        and design.get("adapter_class") == EXPECTED_CLASS
        and design.get("broker_mode") == "PAPER"
        and design.get("host") == "127.0.0.1"
        and design.get("port") == 4002
        and design.get("asset_type") == "STK"
        and design.get("order_type") == "LMT"
        and design.get("time_in_force") == "DAY"
        and design.get("planned_methods") == EXPECTED_METHODS
        and design.get("market_order_allowed") is False
        and design.get("short_selling_allowed") is False
        and design.get("fractional_quantity_allowed") is False
        and design.get("credentials_allowed") is False
        and design.get("raw_account_id_allowed") is False
        and _permissions_false(design)
        and design.get(
            "requires_independent_design_review"
        )
        is True
        and design.get(
            "signed_design_attestation_required"
        )
        is True
        and design.get("next_gate") == DESIGN_NEXT_GATE
    )
    if not design_safe:
        return _blocked("IMPLEMENTATION_DESIGN_POLICY_INVALID")

    design_sha = canonical_json_sha256(design)
    if design_sha is None:
        return _blocked("IMPLEMENTATION_DESIGN_DIGEST_UNAVAILABLE")

    return {
        "engine": ENGINE_VERSION,
        "status": "DESIGN_VALIDATED_NON_EXECUTABLE",
        "reason": "IMPLEMENTATION_DESIGN_REVIEW_REQUIRED",
        "design_validated": True,
        "source_attestation_verified": True,
        "source_review_id": review_id,
        "source_git_sha": source_git_sha,
        "source_sha256": attested_source_sha,
        "source_attestation_sha256": source_attestation_sha,
        "design_sha256": design_sha,
        "independent_design_review_required": True,
        "signed_design_attestation_required": True,
        **{
            name: False
            for name in PERMISSION_FLAGS
        },
        "next_gate": DESIGN_NEXT_GATE,
    }
