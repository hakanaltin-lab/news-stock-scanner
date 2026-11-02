"""G8.17 non-attesting handoff for independent adapter design review.

This gate revalidates the exact G8.16 non-executable implementation design and
prepares an unsigned REVIEW_REQUIRED package for an independent human reviewer.
It never self-attests design safety and never enables implementation or orders.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from uuid import UUID

from engines.paper_adapter_implementation_design import (
    DESIGN_FIELDS,
    DESIGN_ID,
    DESIGN_NEXT_GATE,
    ENGINE_VERSION as DESIGN_ENGINE_VERSION,
    PERMISSION_FLAGS,
    canonical_json_sha256,
)
from engines.paper_adapter_source_review import (
    EXPECTED_CLASS,
    SKELETON_VERSION,
)


ENGINE_VERSION = "AURORA G8.17 Adapter Implementation Design Handoff"
REQUEST_TYPE = "AURORA_ADAPTER_IMPLEMENTATION_DESIGN_REVIEW_REQUEST_V1"
ATTESTATION_TYPE = "AURORA_IBKR_PAPER_ADAPTER_IMPLEMENTATION_DESIGN_REVIEW_V1"
SIGNATURE_ALGORITHM = "ED25519"

DESIGN_REVIEW_FIELDS = {
    "engine",
    "status",
    "reason",
    "design_validated",
    "source_attestation_verified",
    "source_review_id",
    "source_git_sha",
    "source_sha256",
    "source_attestation_sha256",
    "design_sha256",
    "independent_design_review_required",
    "signed_design_attestation_required",
    *PERMISSION_FLAGS,
    "next_gate",
}


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
        "request_type": REQUEST_TYPE,
        "status": "BLOCKED",
        "reason": reason,
        "ready_for_independent_design_review": False,
        "design_revalidated": False,
        "design_attestation_verified": False,
        "operator_asserts_design_safe": False,
        "design_review_artifact_sha256": None,
        "review_request_sha256": None,
        "review_request": None,
        "unsigned_attestation_template": None,
        "independent_design_review_required": True,
        "signed_design_attestation_required": True,
        **{
            name: False
            for name in PERMISSION_FLAGS
        },
        "next_gate": "REPAIR_IMPLEMENTATION_DESIGN_REVIEW_HANDOFF",
    }


def evaluate_implementation_design_handoff(
    design_review,
    design,
    *,
    now=None,
):
    now = (
        now.astimezone(timezone.utc)
        if isinstance(now, datetime)
        and now.tzinfo is not None
        else datetime.now(timezone.utc)
    )

    if not isinstance(design_review, dict):
        return _blocked("DESIGN_REVIEW_RESULT_INVALID")
    if not isinstance(design, dict):
        return _blocked("DESIGN_ARTIFACT_INVALID")

    if set(design_review) != DESIGN_REVIEW_FIELDS:
        return _blocked("DESIGN_REVIEW_FIELD_SET_INVALID")
    if set(design) != DESIGN_FIELDS:
        return _blocked("DESIGN_FIELD_SET_INVALID")

    design_safe = (
        design_review.get("engine")
        == DESIGN_ENGINE_VERSION
        and design_review.get("status")
        == "DESIGN_VALIDATED_NON_EXECUTABLE"
        and design_review.get("reason")
        == "IMPLEMENTATION_DESIGN_REVIEW_REQUIRED"
        and design_review.get("design_validated") is True
        and design_review.get(
            "source_attestation_verified"
        )
        is True
        and design_review.get(
            "independent_design_review_required"
        )
        is True
        and design_review.get(
            "signed_design_attestation_required"
        )
        is True
        and design_review.get("next_gate")
        == DESIGN_NEXT_GATE
        and _permissions_false(design_review)
        and design.get("schema_version") == 1
        and design.get("design_id") == DESIGN_ID
        and design.get("design_status") == "REVIEW_REQUIRED"
        and design.get("next_gate") == DESIGN_NEXT_GATE
        and design.get(
            "requires_independent_design_review"
        )
        is True
        and design.get(
            "signed_design_attestation_required"
        )
        is True
        and _permissions_false(design)
    )
    if not design_safe:
        return _blocked("DESIGN_NOT_SAFE_FOR_HANDOFF")

    design_sha256 = canonical_json_sha256(
        design
    )
    recorded_design_sha256 = _sha256(
        design_review.get("design_sha256")
    )
    if (
        design_sha256 is None
        or recorded_design_sha256 is None
        or design_sha256 != recorded_design_sha256
    ):
        return _blocked("DESIGN_DIGEST_NOT_BOUND")

    source_review_id = _uuid4(
        design_review.get("source_review_id")
    )
    source_git_sha = _git_sha(
        design_review.get("source_git_sha")
    )
    source_sha256 = _sha256(
        design_review.get("source_sha256")
    )
    source_attestation_sha256 = _sha256(
        design_review.get(
            "source_attestation_sha256"
        )
    )
    if (
        source_review_id is None
        or source_git_sha is None
        or source_sha256 is None
        or source_attestation_sha256 is None
    ):
        return _blocked("DESIGN_SOURCE_BINDING_INVALID")

    design_review_artifact_sha256 = (
        canonical_json_sha256(
            design_review
        )
    )
    if design_review_artifact_sha256 is None:
        return _blocked(
            "DESIGN_REVIEW_DIGEST_UNAVAILABLE"
        )

    request = {
        "request_schema_version": 1,
        "request_type": REQUEST_TYPE,
        "requested_control": ATTESTATION_TYPE,
        "generated_at_utc": now.isoformat(),
        "design_review_artifact_sha256": (
            design_review_artifact_sha256
        ),
        "design_sha256": design_sha256,
        "source_review_id": source_review_id,
        "source_git_sha": source_git_sha,
        "source_sha256": source_sha256,
        "source_attestation_sha256": (
            source_attestation_sha256
        ),
        "design_id": DESIGN_ID,
        "skeleton_version": SKELETON_VERSION,
        "adapter_class": EXPECTED_CLASS,
        "operator_asserts_design_safe": False,
        "requires_human_design_review": True,
        "signed_design_attestation_required": True,
        **{
            name: False
            for name in PERMISSION_FLAGS
        },
    }
    review_request_sha256 = (
        canonical_json_sha256(
            request
        )
    )
    if review_request_sha256 is None:
        return _blocked(
            "DESIGN_REVIEW_REQUEST_DIGEST_UNAVAILABLE"
        )

    template = {
        "schema_version": 1,
        "attestation_type": ATTESTATION_TYPE,
        "design_review_id": None,
        "decision": "REVIEW_REQUIRED",
        "reviewer_id": None,
        "captured_at_utc": None,
        "expires_at_utc": None,
        "design_review_artifact_sha256": (
            design_review_artifact_sha256
        ),
        "review_request_sha256": (
            review_request_sha256
        ),
        "design_sha256": design_sha256,
        "source_review_id": source_review_id,
        "source_git_sha": source_git_sha,
        "source_sha256": source_sha256,
        "source_attestation_sha256": (
            source_attestation_sha256
        ),
        "design_id": DESIGN_ID,
        "skeleton_version": SKELETON_VERSION,
        "adapter_class": EXPECTED_CLASS,
        "reviewer_confirms_design_non_executable": None,
        "reviewer_confirms_fail_closed_defaults": None,
        "reviewer_confirms_no_credentials_or_raw_accounts": None,
        "reviewer_evidence_sha256": None,
        "signature_algorithm": SIGNATURE_ALGORITHM,
        "signature_b64": None,
    }

    return {
        "engine": ENGINE_VERSION,
        "request_type": REQUEST_TYPE,
        "status": "READY_FOR_INDEPENDENT_IMPLEMENTATION_DESIGN_REVIEW",
        "reason": "HUMAN_IMPLEMENTATION_DESIGN_REVIEW_REQUIRED",
        "ready_for_independent_design_review": True,
        "design_revalidated": True,
        "design_attestation_verified": False,
        "operator_asserts_design_safe": False,
        "design_review_artifact_sha256": (
            design_review_artifact_sha256
        ),
        "review_request_sha256": (
            review_request_sha256
        ),
        "review_request": request,
        "unsigned_attestation_template": template,
        "reviewer_must_set": [
            "design_review_id",
            "decision=ATTESTED only after independent review",
            "reviewer_id",
            "captured_at_utc",
            "expires_at_utc",
            "reviewer_confirms_design_non_executable=true",
            "reviewer_confirms_fail_closed_defaults=true",
            "reviewer_confirms_no_credentials_or_raw_accounts=true",
            "reviewer_evidence_sha256",
            "signature_b64",
        ],
        "independent_design_review_required": True,
        "signed_design_attestation_required": True,
        **{
            name: False
            for name in PERMISSION_FLAGS
        },
        "next_gate": (
            "SIGNED_INDEPENDENT_ADAPTER_IMPLEMENTATION_DESIGN_ATTESTATION_REQUIRED"
        ),
    }
