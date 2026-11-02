"""G8.14 non-attesting handoff for independent Paper adapter source review.

This gate revalidates the exact G8.13 source-review artifact and tracked source,
then prepares a sanitized REVIEW_REQUIRED package for an independent human
reviewer. It never self-attests source safety and never enables execution.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import math
from uuid import UUID

from engines.paper_adapter_source_review import (
    ENGINE_VERSION as SOURCE_REVIEW_ENGINE_VERSION,
    EXPECTED_CLASS,
    POLICY_VERSION as SOURCE_POLICY_VERSION,
    SKELETON_VERSION,
)


ENGINE_VERSION = "AURORA G8.14 Adapter Source Review Handoff"
REQUEST_TYPE = "AURORA_ADAPTER_SOURCE_REVIEW_REQUEST_V1"
ATTESTATION_TYPE = "AURORA_IBKR_PAPER_ADAPTER_SOURCE_REVIEW_V1"
SIGNATURE_ALGORITHM = "ED25519"
DEFAULT_MAX_SOURCE_REVIEW_AGE_SECONDS = 900

_PERMISSION_FLAGS = (
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

_SOURCE_REVIEW_FIELDS = {
    "engine",
    "policy_version",
    "generated_at",
    "status",
    "reason",
    "source_policy_validated",
    "runtime_prerequisite_sha256",
    "source_sha256",
    "skeleton_version",
    "adapter_class",
    "git_sha",
    "authorization_id",
    "evidence_run_id",
    "gce_instance_id",
    "g0_g1_proof_sha256",
    "g2_paper_read_only_proof_sha256",
    "gateway_read_only_attestation_sha256",
    "paper_account_fingerprints",
    "source_policy_sha256",
    "runtime_prerequisite_age_seconds",
    "independent_source_review_required",
    *_PERMISSION_FLAGS,
    "next_gate",
}


def _canonical_digest(payload):
    try:
        encoded = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, OverflowError):
        return None
    return hashlib.sha256(encoded).hexdigest()


def _source_digest(source_text):
    if not isinstance(source_text, str):
        return None
    return hashlib.sha256(
        source_text.encode("utf-8")
    ).hexdigest()


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
    return text if parsed.version == 4 and str(parsed) == text else None


def _instance_id(value):
    text = str(value or "").strip()
    if (
        not text.isdigit()
        or not 6 <= len(text) <= 30
        or text[0] == "0"
    ):
        return None
    return text


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


def _fingerprints(value):
    if not isinstance(value, list) or len(value) != 1:
        return None
    item = value[0]
    if (
        not isinstance(item, str)
        or len(item) != 15
        or not item.startswith("IBKR-")
        or any(
            character not in "0123456789ABCDEF"
            for character in item[5:]
        )
    ):
        return None
    return [item]


def _permissions_false(payload):
    return (
        isinstance(payload, dict)
        and all(
            name in payload
            and payload.get(name) is False
            for name in _PERMISSION_FLAGS
        )
    )


def _blocked(reason):
    return {
        "engine": ENGINE_VERSION,
        "request_type": REQUEST_TYPE,
        "status": "BLOCKED",
        "reason": reason,
        "ready_for_independent_source_review": False,
        "source_policy_revalidated": False,
        "source_attestation_verified": False,
        "operator_asserts_source_safe": False,
        "source_review_artifact_sha256": None,
        "review_request": None,
        "unsigned_attestation_template": None,
        "independent_source_review_required": True,
        "signed_source_attestation_required": True,
        "implementation_allowed": False,
        "connection_allowed": False,
        "broker_request_materialization_allowed": False,
        "broker_order_object_allowed": False,
        "automatic_retry_allowed": False,
        "automatic_cancel_allowed": False,
        "automatic_modify_allowed": False,
        "broker_submission_allowed": False,
        "paper_order_submission_allowed": False,
        "live_execution_allowed": False,
        "automatic_promotion_allowed": False,
        "real_money_trading_allowed": False,
        "next_gate": "REPAIR_ADAPTER_SOURCE_REVIEW_HANDOFF",
    }


def _source_policy_payload(source_review):
    return {
        "policy_version": source_review.get(
            "policy_version"
        ),
        "runtime_prerequisite_sha256": source_review.get(
            "runtime_prerequisite_sha256"
        ),
        "source_sha256": source_review.get(
            "source_sha256"
        ),
        "skeleton_version": source_review.get(
            "skeleton_version"
        ),
        "adapter_class": source_review.get(
            "adapter_class"
        ),
        "git_sha": source_review.get(
            "git_sha"
        ),
        "authorization_id": source_review.get(
            "authorization_id"
        ),
        "evidence_run_id": source_review.get(
            "evidence_run_id"
        ),
        "gce_instance_id": source_review.get(
            "gce_instance_id"
        ),
        "g0_g1_proof_sha256": source_review.get(
            "g0_g1_proof_sha256"
        ),
        "g2_paper_read_only_proof_sha256": source_review.get(
            "g2_paper_read_only_proof_sha256"
        ),
        "gateway_read_only_attestation_sha256": source_review.get(
            "gateway_read_only_attestation_sha256"
        ),
        "paper_account_fingerprints": source_review.get(
            "paper_account_fingerprints"
        ),
    }


def evaluate_source_review_handoff(
    source_review,
    source_text,
    current_git_sha,
    repository_clean,
    now=None,
    max_source_review_age_seconds=(
        DEFAULT_MAX_SOURCE_REVIEW_AGE_SECONDS
    ),
):
    now = (
        now.astimezone(timezone.utc)
        if isinstance(now, datetime)
        and now.tzinfo is not None
        else datetime.now(timezone.utc)
    )

    if not isinstance(source_review, dict):
        return _blocked(
            "SOURCE_REVIEW_ARTIFACT_INVALID"
        )

    if (
        type(max_source_review_age_seconds) is not int
        or not 60 <= max_source_review_age_seconds <= 3600
    ):
        return _blocked(
            "SOURCE_REVIEW_MAX_AGE_INVALID"
        )

    exact_fields = (
        set(source_review)
        == _SOURCE_REVIEW_FIELDS
    )
    generated_at = _utc_datetime(
        source_review.get("generated_at")
    )
    age_seconds = (
        (now - generated_at).total_seconds()
        if generated_at is not None
        else None
    )
    current_git_sha = _git_sha(
        current_git_sha
    )
    artifact_git_sha = _git_sha(
        source_review.get("git_sha")
    )
    source_sha256 = _sha256(
        source_review.get("source_sha256")
    )
    actual_source_sha256 = _source_digest(
        source_text
    )
    fingerprints = _fingerprints(
        source_review.get(
            "paper_account_fingerprints"
        )
    )

    runtime_age = source_review.get(
        "runtime_prerequisite_age_seconds"
    )
    runtime_age_valid = (
        isinstance(runtime_age, (int, float))
        and not isinstance(runtime_age, bool)
        and math.isfinite(float(runtime_age))
        and 0 <= float(runtime_age) <= 300
    )

    source_policy_sha256 = _sha256(
        source_review.get(
            "source_policy_sha256"
        )
    )
    recomputed_policy_sha256 = (
        _canonical_digest(
            _source_policy_payload(
                source_review
            )
        )
    )

    valid = (
        exact_fields
        and source_review.get("engine")
        == SOURCE_REVIEW_ENGINE_VERSION
        and source_review.get("policy_version")
        == SOURCE_POLICY_VERSION
        and source_review.get("status")
        == "SOURCE_POLICY_VALIDATED_NON_EXECUTABLE"
        and source_review.get("reason")
        == "REVIEW_SKELETON_SOURCE_HARD_DISABLED"
        and source_review.get(
            "source_policy_validated"
        )
        is True
        and source_review.get(
            "independent_source_review_required"
        )
        is True
        and source_review.get("next_gate")
        == "INDEPENDENT_ADAPTER_SOURCE_REVIEW_REQUIRED"
        and _permissions_false(source_review)
        and source_review.get(
            "skeleton_version"
        )
        == SKELETON_VERSION
        and source_review.get(
            "adapter_class"
        )
        == EXPECTED_CLASS
        and _sha256(
            source_review.get(
                "runtime_prerequisite_sha256"
            )
        )
        is not None
        and source_sha256 is not None
        and actual_source_sha256 is not None
        and source_sha256 == actual_source_sha256
        and source_policy_sha256 is not None
        and recomputed_policy_sha256 is not None
        and source_policy_sha256
        == recomputed_policy_sha256
        and _uuid4(
            source_review.get(
                "authorization_id"
            )
        )
        is not None
        and _uuid4(
            source_review.get(
                "evidence_run_id"
            )
        )
        is not None
        and _instance_id(
            source_review.get(
                "gce_instance_id"
            )
        )
        is not None
        and _sha256(
            source_review.get(
                "g0_g1_proof_sha256"
            )
        )
        is not None
        and _sha256(
            source_review.get(
                "g2_paper_read_only_proof_sha256"
            )
        )
        is not None
        and _sha256(
            source_review.get(
                "gateway_read_only_attestation_sha256"
            )
        )
        is not None
        and fingerprints is not None
        and runtime_age_valid
        and generated_at is not None
        and age_seconds is not None
        and -2 <= age_seconds
        <= max_source_review_age_seconds
        and artifact_git_sha is not None
        and current_git_sha is not None
        and artifact_git_sha
        == current_git_sha
        and repository_clean is True
    )
    if not valid:
        return _blocked(
            "SOURCE_REVIEW_ARTIFACT_NOT_SAFE_FOR_HANDOFF"
        )

    source_review_artifact_sha256 = (
        _canonical_digest(
            source_review
        )
    )
    if source_review_artifact_sha256 is None:
        return _blocked(
            "SOURCE_REVIEW_ARTIFACT_DIGEST_UNAVAILABLE"
        )

    review_request = {
        "request_schema_version": 1,
        "request_type": REQUEST_TYPE,
        "requested_control": ATTESTATION_TYPE,
        "generated_at_utc": now.isoformat(),
        "git_sha": artifact_git_sha,
        "source_review_artifact_sha256": (
            source_review_artifact_sha256
        ),
        "runtime_prerequisite_sha256": source_review.get(
            "runtime_prerequisite_sha256"
        ),
        "source_sha256": source_sha256,
        "source_policy_sha256": source_policy_sha256,
        "skeleton_version": SKELETON_VERSION,
        "adapter_class": EXPECTED_CLASS,
        "authorization_id": source_review.get(
            "authorization_id"
        ),
        "evidence_run_id": source_review.get(
            "evidence_run_id"
        ),
        "gce_instance_id": source_review.get(
            "gce_instance_id"
        ),
        "g0_g1_proof_sha256": source_review.get(
            "g0_g1_proof_sha256"
        ),
        "g2_paper_read_only_proof_sha256": source_review.get(
            "g2_paper_read_only_proof_sha256"
        ),
        "gateway_read_only_attestation_sha256": source_review.get(
            "gateway_read_only_attestation_sha256"
        ),
        "paper_account_fingerprints": fingerprints,
        "operator_asserts_source_safe": False,
        "requires_human_source_review": True,
        "signed_source_attestation_required": True,
        **{
            name: False
            for name in _PERMISSION_FLAGS
        },
    }

    review_request_sha256 = _canonical_digest(
        review_request
    )
    if review_request_sha256 is None:
        return _blocked(
            "SOURCE_REVIEW_REQUEST_DIGEST_UNAVAILABLE"
        )

    unsigned_template = {
        "schema_version": 1,
        "attestation_type": ATTESTATION_TYPE,
        "review_id": None,
        "decision": "REVIEW_REQUIRED",
        "reviewer_id": None,
        "captured_at_utc": None,
        "expires_at_utc": None,
        "git_sha": artifact_git_sha,
        "source_review_artifact_sha256": (
            source_review_artifact_sha256
        ),
        "review_request_sha256": review_request_sha256,
        "runtime_prerequisite_sha256": source_review.get(
            "runtime_prerequisite_sha256"
        ),
        "source_sha256": source_sha256,
        "source_policy_sha256": source_policy_sha256,
        "skeleton_version": SKELETON_VERSION,
        "adapter_class": EXPECTED_CLASS,
        "reviewer_confirms_source_non_executable": None,
        "reviewer_confirms_scope_frozen": None,
        "reviewer_evidence_sha256": None,
        "signature_algorithm": SIGNATURE_ALGORITHM,
        "signature_b64": None,
    }

    return {
        "engine": ENGINE_VERSION,
        "request_type": REQUEST_TYPE,
        "generated_at": now.isoformat(),
        "status": "READY_FOR_INDEPENDENT_ADAPTER_SOURCE_REVIEW",
        "reason": "HUMAN_SOURCE_REVIEW_REQUIRED",
        "ready_for_independent_source_review": True,
        "source_policy_revalidated": True,
        "source_attestation_verified": False,
        "operator_asserts_source_safe": False,
        "source_review_artifact_sha256": (
            source_review_artifact_sha256
        ),
        "review_request_sha256": review_request_sha256,
        "review_request": review_request,
        "unsigned_attestation_template": (
            unsigned_template
        ),
        "reviewer_must_set": [
            "review_id",
            "decision=ATTESTED only after independent source review",
            "reviewer_id",
            "captured_at_utc",
            "expires_at_utc",
            "reviewer_confirms_source_non_executable=true only after review",
            "reviewer_confirms_scope_frozen=true only after review",
            "reviewer_evidence_sha256",
            "signature_b64",
        ],
        "independent_source_review_required": True,
        "signed_source_attestation_required": True,
        "implementation_allowed": False,
        "connection_allowed": False,
        "broker_request_materialization_allowed": False,
        "broker_order_object_allowed": False,
        "automatic_retry_allowed": False,
        "automatic_cancel_allowed": False,
        "automatic_modify_allowed": False,
        "broker_submission_allowed": False,
        "paper_order_submission_allowed": False,
        "live_execution_allowed": False,
        "automatic_promotion_allowed": False,
        "real_money_trading_allowed": False,
        "next_gate": (
            "SIGNED_INDEPENDENT_ADAPTER_SOURCE_ATTESTATION_REQUIRED"
        ),
    }
