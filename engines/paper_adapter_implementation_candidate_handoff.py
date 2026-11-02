"""G8.20 non-attesting handoff for independent implementation-candidate review."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from uuid import UUID

from engines.paper_adapter_implementation_candidate_review import (
    CANDIDATE_VERSION,
    ENGINE_VERSION as CANDIDATE_ENGINE_VERSION,
    EXPECTED_CLASS,
    NEXT_GATE as CANDIDATE_NEXT_GATE,
    PERMISSION_FLAGS,
    validate_candidate_source,
)


ENGINE_VERSION = "AURORA G8.20 Adapter Implementation Candidate Handoff"
REQUEST_TYPE = "AURORA_ADAPTER_IMPLEMENTATION_CANDIDATE_REVIEW_REQUEST_V1"
ATTESTATION_TYPE = "AURORA_IBKR_PAPER_ADAPTER_IMPLEMENTATION_CANDIDATE_REVIEW_V1"
SIGNATURE_ALGORITHM = "ED25519"

CANDIDATE_REVIEW_FIELDS = {
    "engine",
    "status",
    "reason",
    "candidate_validated",
    "design_attestation_verified",
    "candidate_version",
    "adapter_class",
    "candidate_source_sha256",
    "design_attestation_sha256",
    "design_sha256",
    "design_review_id",
    "source_attestation_sha256",
    "source_git_sha",
    "independent_candidate_review_required",
    *PERMISSION_FLAGS,
    "next_gate",
}


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


def _git_sha(value):
    text = str(value or "").strip().lower()
    if (
        len(text) != 40
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
        "ready_for_independent_candidate_review": False,
        "candidate_revalidated": False,
        "candidate_attestation_verified": False,
        "operator_asserts_candidate_safe": False,
        "candidate_review_artifact_sha256": None,
        "review_request_sha256": None,
        "review_request": None,
        "unsigned_attestation_template": None,
        "independent_candidate_review_required": True,
        "signed_candidate_attestation_required": True,
        **{
            name: False
            for name in PERMISSION_FLAGS
        },
        "next_gate": "REPAIR_IMPLEMENTATION_CANDIDATE_REVIEW_HANDOFF",
    }


def evaluate_candidate_review_handoff(
    candidate_review,
    candidate_source,
    *,
    now=None,
):
    now = (
        now.astimezone(timezone.utc)
        if isinstance(now, datetime)
        and now.tzinfo is not None
        else datetime.now(timezone.utc)
    )

    if not isinstance(candidate_review, dict):
        return _blocked("CANDIDATE_REVIEW_RESULT_INVALID")
    if set(candidate_review) != CANDIDATE_REVIEW_FIELDS:
        return _blocked("CANDIDATE_REVIEW_FIELD_SET_INVALID")
    if not isinstance(candidate_source, str) or not candidate_source:
        return _blocked("CANDIDATE_SOURCE_UNAVAILABLE")

    candidate_safe = (
        candidate_review.get("engine")
        == CANDIDATE_ENGINE_VERSION
        and candidate_review.get("status")
        == "IMPLEMENTATION_CANDIDATE_VALIDATED_NON_EXECUTABLE"
        and candidate_review.get("reason")
        == "INDEPENDENT_IMPLEMENTATION_CANDIDATE_REVIEW_REQUIRED"
        and candidate_review.get("candidate_validated") is True
        and candidate_review.get(
            "design_attestation_verified"
        )
        is True
        and candidate_review.get("candidate_version")
        == CANDIDATE_VERSION
        and candidate_review.get("adapter_class")
        == EXPECTED_CLASS
        and candidate_review.get(
            "independent_candidate_review_required"
        )
        is True
        and candidate_review.get("next_gate")
        == CANDIDATE_NEXT_GATE
        and _permissions_false(candidate_review)
    )
    if not candidate_safe:
        return _blocked(
            "CANDIDATE_NOT_SAFE_FOR_HANDOFF"
        )

    source_valid, source_reason = validate_candidate_source(
        candidate_source
    )
    if not source_valid:
        return _blocked(
            source_reason
            or "CANDIDATE_SOURCE_POLICY_INVALID"
        )

    candidate_source_sha256 = hashlib.sha256(
        candidate_source.encode("utf-8")
    ).hexdigest()
    recorded_source_sha256 = _sha256(
        candidate_review.get(
            "candidate_source_sha256"
        )
    )
    if (
        recorded_source_sha256 is None
        or candidate_source_sha256
        != recorded_source_sha256
    ):
        return _blocked(
            "CANDIDATE_SOURCE_DIGEST_NOT_BOUND"
        )

    design_attestation_sha256 = _sha256(
        candidate_review.get(
            "design_attestation_sha256"
        )
    )
    design_sha256 = _sha256(
        candidate_review.get(
            "design_sha256"
        )
    )
    design_review_id = _uuid4(
        candidate_review.get(
            "design_review_id"
        )
    )
    source_attestation_sha256 = _sha256(
        candidate_review.get(
            "source_attestation_sha256"
        )
    )
    source_git_sha = _git_sha(
        candidate_review.get(
            "source_git_sha"
        )
    )
    if (
        design_attestation_sha256 is None
        or design_sha256 is None
        or design_review_id is None
        or source_attestation_sha256 is None
        or source_git_sha is None
    ):
        return _blocked(
            "CANDIDATE_BINDING_INVALID"
        )

    candidate_review_artifact_sha256 = (
        canonical_json_sha256(
            candidate_review
        )
    )
    if candidate_review_artifact_sha256 is None:
        return _blocked(
            "CANDIDATE_REVIEW_DIGEST_UNAVAILABLE"
        )

    request = {
        "request_schema_version": 1,
        "request_type": REQUEST_TYPE,
        "requested_control": ATTESTATION_TYPE,
        "generated_at_utc": now.isoformat(),
        "candidate_review_artifact_sha256": (
            candidate_review_artifact_sha256
        ),
        "candidate_source_sha256": (
            candidate_source_sha256
        ),
        "candidate_version": CANDIDATE_VERSION,
        "adapter_class": EXPECTED_CLASS,
        "design_attestation_sha256": (
            design_attestation_sha256
        ),
        "design_sha256": design_sha256,
        "design_review_id": design_review_id,
        "source_attestation_sha256": (
            source_attestation_sha256
        ),
        "source_git_sha": source_git_sha,
        "operator_asserts_candidate_safe": False,
        "requires_human_candidate_review": True,
        "signed_candidate_attestation_required": True,
        **{
            name: False
            for name in PERMISSION_FLAGS
        },
    }
    review_request_sha256 = canonical_json_sha256(
        request
    )
    if review_request_sha256 is None:
        return _blocked(
            "CANDIDATE_REVIEW_REQUEST_DIGEST_UNAVAILABLE"
        )

    template = {
        "schema_version": 1,
        "attestation_type": ATTESTATION_TYPE,
        "candidate_review_id": None,
        "decision": "REVIEW_REQUIRED",
        "reviewer_id": None,
        "captured_at_utc": None,
        "expires_at_utc": None,
        "candidate_review_artifact_sha256": (
            candidate_review_artifact_sha256
        ),
        "review_request_sha256": (
            review_request_sha256
        ),
        "candidate_source_sha256": (
            candidate_source_sha256
        ),
        "candidate_version": CANDIDATE_VERSION,
        "adapter_class": EXPECTED_CLASS,
        "design_attestation_sha256": (
            design_attestation_sha256
        ),
        "design_sha256": design_sha256,
        "design_review_id": design_review_id,
        "source_attestation_sha256": (
            source_attestation_sha256
        ),
        "source_git_sha": source_git_sha,
        "reviewer_confirms_candidate_non_executable": None,
        "reviewer_confirms_broker_methods_hard_disabled": None,
        "reviewer_confirms_no_broker_imports": None,
        "reviewer_evidence_sha256": None,
        "signature_algorithm": SIGNATURE_ALGORITHM,
        "signature_b64": None,
    }

    return {
        "engine": ENGINE_VERSION,
        "request_type": REQUEST_TYPE,
        "status": "READY_FOR_INDEPENDENT_IMPLEMENTATION_CANDIDATE_REVIEW",
        "reason": "HUMAN_IMPLEMENTATION_CANDIDATE_REVIEW_REQUIRED",
        "ready_for_independent_candidate_review": True,
        "candidate_revalidated": True,
        "candidate_attestation_verified": False,
        "operator_asserts_candidate_safe": False,
        "candidate_review_artifact_sha256": (
            candidate_review_artifact_sha256
        ),
        "review_request_sha256": (
            review_request_sha256
        ),
        "review_request": request,
        "unsigned_attestation_template": template,
        "reviewer_must_set": [
            "candidate_review_id",
            "decision=ATTESTED only after independent review",
            "reviewer_id",
            "captured_at_utc",
            "expires_at_utc",
            "reviewer_confirms_candidate_non_executable=true",
            "reviewer_confirms_broker_methods_hard_disabled=true",
            "reviewer_confirms_no_broker_imports=true",
            "reviewer_evidence_sha256",
            "signature_b64",
        ],
        "independent_candidate_review_required": True,
        "signed_candidate_attestation_required": True,
        **{
            name: False
            for name in PERMISSION_FLAGS
        },
        "next_gate": (
            "SIGNED_INDEPENDENT_ADAPTER_IMPLEMENTATION_CANDIDATE_ATTESTATION_REQUIRED"
        ),
    }
