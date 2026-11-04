"""G8.15 verifier for independently signed Paper adapter source review.

AURORA never creates this attestation and never possesses the reviewer private
key. This module validates parsed evidence and returns only a review-state
advance; it does not enable implementation, broker connectivity, or orders.
"""

from __future__ import annotations

import base64
import binascii
from datetime import datetime, timezone
import hashlib
import json
import re
from uuid import UUID

from engines.paper_adapter_source_handoff import (
    ATTESTATION_TYPE,
    ENGINE_VERSION as HANDOFF_ENGINE_VERSION,
    REQUEST_TYPE,
    SIGNATURE_ALGORITHM,
)
from engines.paper_adapter_source_review import (
    ENGINE_VERSION as SOURCE_REVIEW_ENGINE_VERSION,
    EXPECTED_CLASS,
    POLICY_VERSION as SOURCE_POLICY_VERSION,
    SKELETON_VERSION,
)


ENGINE_VERSION = "AURORA G8.15 Adapter Source Attestation Verifier"

ARTIFACT_FIELDS = {
    "schema_version",
    "attestation_type",
    "review_id",
    "decision",
    "reviewer_id",
    "captured_at_utc",
    "expires_at_utc",
    "git_sha",
    "source_review_artifact_sha256",
    "review_request_sha256",
    "runtime_prerequisite_sha256",
    "source_sha256",
    "source_policy_sha256",
    "skeleton_version",
    "adapter_class",
    "reviewer_confirms_source_non_executable",
    "reviewer_confirms_scope_frozen",
    "reviewer_evidence_sha256",
    "signature_algorithm",
    "signature_b64",
}

POLICY_FIELDS = {
    "policy_version",
    "reviewer_id",
    "public_key_sha256",
    "expected_skeleton_version",
    "expected_adapter_class",
    "max_attestation_age_seconds",
    "allowed_clock_skew_seconds",
}

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

HANDOFF_FIELDS = {
    "engine",
    "request_type",
    "generated_at",
    "status",
    "reason",
    "ready_for_independent_source_review",
    "source_policy_revalidated",
    "source_attestation_verified",
    "operator_asserts_source_safe",
    "source_review_artifact_sha256",
    "review_request_sha256",
    "review_request",
    "unsigned_attestation_template",
    "reviewer_must_set",
    "independent_source_review_required",
    "signed_source_attestation_required",
    *PERMISSION_FLAGS,
    "next_gate",
}

REVIEW_REQUEST_FIELDS = {
    "request_schema_version",
    "request_type",
    "requested_control",
    "generated_at_utc",
    "git_sha",
    "source_review_artifact_sha256",
    "runtime_prerequisite_sha256",
    "source_sha256",
    "source_policy_sha256",
    "skeleton_version",
    "adapter_class",
    "authorization_id",
    "evidence_run_id",
    "g2_probe_stage",
    "gce_instance_id",
    "g0_g1_proof_sha256",
    "g2_paper_read_only_proof_sha256",
    "gateway_read_only_attestation_sha256",
    "paper_account_fingerprints",
    "operator_asserts_source_safe",
    "requires_human_source_review",
    "signed_source_attestation_required",
    *PERMISSION_FLAGS,
}

SOURCE_REVIEW_FIELDS = {
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
    "g2_probe_stage",
    "gce_instance_id",
    "g0_g1_proof_sha256",
    "g2_paper_read_only_proof_sha256",
    "gateway_read_only_attestation_sha256",
    "paper_account_fingerprints",
    "source_policy_sha256",
    "runtime_prerequisite_age_seconds",
    "independent_source_review_required",
    *PERMISSION_FLAGS,
    "next_gate",
}

_HEX_40 = re.compile(r"^[0-9a-f]{40}$")
_HEX_64 = re.compile(r"^[0-9a-f]{64}$")
_REVIEWER_ID = re.compile(r"^[A-Za-z0-9._@+-]{3,128}$")


def canonical_json_sha256(payload):
    if not isinstance(payload, dict):
        return None
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


def canonical_signed_payload(artifact):
    if not isinstance(artifact, dict):
        return None
    payload = {
        key: value
        for key, value in artifact.items()
        if key != "signature_b64"
    }
    try:
        return json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, OverflowError):
        return None


def decode_signature(value):
    text = str(value or "").strip()
    try:
        decoded = base64.b64decode(
            text,
            validate=True,
        )
    except (binascii.Error, ValueError):
        return None
    return decoded if len(decoded) == 64 else None


def _sha256(value):
    text = str(value or "").strip().lower()
    return text if _HEX_64.fullmatch(text) else None


def _git_sha(value):
    text = str(value or "").strip().lower()
    return text if _HEX_40.fullmatch(text) else None


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


def _blocked(reason, checks=None):
    return {
        "engine": ENGINE_VERSION,
        "status": "BLOCKED",
        "verified": False,
        "adapter_source_independently_attested": False,
        "reason": reason,
        "checks": checks or {},
        "review_id": None,
        "reviewer_id": None,
        "captured_at_utc": None,
        "expires_at_utc": None,
        "git_sha": None,
        "source_review_artifact_sha256": None,
        "review_request_sha256": None,
        "source_sha256": None,
        "source_policy_sha256": None,
        "source_attestation_sha256": None,
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
        "next_gate": "REPAIR_SIGNED_ADAPTER_SOURCE_ATTESTATION",
    }


def evaluate_source_attestation(
    artifact,
    policy,
    public_key_bytes,
    signature_valid,
    handoff,
    source_review,
    source_text,
    current_git_sha,
    repository_clean,
    now=None,
):
    now = (
        now.astimezone(timezone.utc)
        if isinstance(now, datetime)
        and now.tzinfo is not None
        else datetime.now(timezone.utc)
    )

    checks = {}

    def check(name, passed):
        checks[name] = bool(passed)

    artifact_ok = isinstance(artifact, dict)
    policy_ok = isinstance(policy, dict)
    handoff_ok = isinstance(handoff, dict)
    source_review_ok = isinstance(source_review, dict)

    check("artifact_is_object", artifact_ok)
    check("policy_is_object", policy_ok)
    check("handoff_is_object", handoff_ok)
    check("source_review_is_object", source_review_ok)

    artifact = artifact if artifact_ok else {}
    policy = policy if policy_ok else {}
    handoff = handoff if handoff_ok else {}
    source_review = source_review if source_review_ok else {}

    check(
        "artifact_field_set_exact",
        set(artifact) == ARTIFACT_FIELDS,
    )
    check(
        "policy_field_set_exact",
        set(policy) == POLICY_FIELDS,
    )
    check(
        "handoff_field_set_exact",
        set(handoff) == HANDOFF_FIELDS,
    )
    check(
        "source_review_field_set_exact",
        set(source_review) == SOURCE_REVIEW_FIELDS,
    )

    request = (
        handoff.get("review_request")
        if isinstance(
            handoff.get("review_request"),
            dict,
        )
        else {}
    )
    check(
        "review_request_field_set_exact",
        set(request) == REVIEW_REQUEST_FIELDS,
    )

    check(
        "artifact_schema_version",
        type(artifact.get("schema_version")) is int
        and artifact.get("schema_version") == 1,
    )
    check(
        "artifact_type",
        artifact.get("attestation_type")
        == ATTESTATION_TYPE,
    )
    check(
        "decision_attested",
        artifact.get("decision") == "ATTESTED",
    )
    review_id = _uuid4(
        artifact.get("review_id")
    )
    check(
        "review_id_uuid4",
        review_id is not None,
    )
    check(
        "signature_algorithm",
        artifact.get("signature_algorithm")
        == SIGNATURE_ALGORITHM,
    )
    check(
        "signature_encoding_valid",
        decode_signature(
            artifact.get("signature_b64")
        )
        is not None,
    )
    check(
        "ed25519_signature_valid",
        signature_valid is True,
    )

    reviewer_id = str(
        artifact.get("reviewer_id") or ""
    ).strip()
    policy_reviewer_id = str(
        policy.get("reviewer_id") or ""
    ).strip()
    check(
        "policy_version",
        type(policy.get("policy_version")) is int
        and policy.get("policy_version") == 1,
    )
    check(
        "reviewer_id_format",
        bool(
            _REVIEWER_ID.fullmatch(
                reviewer_id
            )
        ),
    )
    check(
        "reviewer_matches_policy",
        reviewer_id
        and reviewer_id == policy_reviewer_id,
    )
    check(
        "policy_skeleton_version",
        policy.get("expected_skeleton_version")
        == SKELETON_VERSION,
    )
    check(
        "policy_adapter_class",
        policy.get("expected_adapter_class")
        == EXPECTED_CLASS,
    )

    public_key_valid = (
        isinstance(public_key_bytes, bytes)
        and b"-----BEGIN PUBLIC KEY-----"
        in public_key_bytes
        and b"PRIVATE KEY" not in public_key_bytes
    )
    public_key_sha256 = (
        hashlib.sha256(
            public_key_bytes
        ).hexdigest()
        if isinstance(public_key_bytes, bytes)
        else ""
    )
    policy_key_sha256 = _sha256(
        policy.get("public_key_sha256")
    )
    check(
        "reviewer_public_key_material_valid",
        public_key_valid,
    )
    check(
        "policy_public_key_sha256_valid",
        policy_key_sha256 is not None
        and policy_key_sha256 != ("0" * 64),
    )
    check(
        "public_key_matches_policy",
        public_key_valid
        and policy_key_sha256 is not None
        and public_key_sha256
        == policy_key_sha256,
    )

    max_age = policy.get(
        "max_attestation_age_seconds"
    )
    clock_skew = policy.get(
        "allowed_clock_skew_seconds"
    )
    max_age_valid = (
        type(max_age) is int
        and 60 <= max_age <= 86400
    )
    clock_skew_valid = (
        type(clock_skew) is int
        and 0 <= clock_skew <= 300
    )
    check(
        "policy_max_age_valid",
        max_age_valid,
    )
    check(
        "policy_clock_skew_valid",
        clock_skew_valid,
    )

    captured = _utc_datetime(
        artifact.get("captured_at_utc")
    )
    expires = _utc_datetime(
        artifact.get("expires_at_utc")
    )
    check(
        "captured_at_valid",
        captured is not None,
    )
    check(
        "expires_at_valid",
        expires is not None,
    )
    if (
        captured is not None
        and expires is not None
        and max_age_valid
        and clock_skew_valid
    ):
        age_seconds = (
            now - captured
        ).total_seconds()
        validity_seconds = (
            expires - captured
        ).total_seconds()
        check(
            "capture_not_in_future",
            age_seconds >= -clock_skew,
        )
        check(
            "attestation_not_expired",
            now <= expires,
        )
        check(
            "attestation_age_within_policy",
            age_seconds <= max_age,
        )
        check(
            "attestation_validity_window_positive",
            validity_seconds > 0,
        )
        check(
            "attestation_validity_window_within_policy",
            validity_seconds <= max_age,
        )
    else:
        for name in (
            "capture_not_in_future",
            "attestation_not_expired",
            "attestation_age_within_policy",
            "attestation_validity_window_positive",
            "attestation_validity_window_within_policy",
        ):
            check(name, False)

    check(
        "reviewer_confirms_source_non_executable",
        artifact.get(
            "reviewer_confirms_source_non_executable"
        )
        is True,
    )
    check(
        "reviewer_confirms_scope_frozen",
        artifact.get(
            "reviewer_confirms_scope_frozen"
        )
        is True,
    )
    reviewer_evidence_sha256 = _sha256(
        artifact.get(
            "reviewer_evidence_sha256"
        )
    )
    check(
        "reviewer_evidence_sha256_valid",
        reviewer_evidence_sha256 is not None
        and reviewer_evidence_sha256
        != ("0" * 64),
    )

    handoff_ready = (
        handoff.get("engine")
        == HANDOFF_ENGINE_VERSION
        and handoff.get("request_type")
        == REQUEST_TYPE
        and handoff.get("status")
        == "READY_FOR_INDEPENDENT_ADAPTER_SOURCE_REVIEW"
        and handoff.get("reason")
        == "HUMAN_SOURCE_REVIEW_REQUIRED"
        and handoff.get(
            "ready_for_independent_source_review"
        )
        is True
        and handoff.get(
            "source_policy_revalidated"
        )
        is True
        and handoff.get(
            "source_attestation_verified"
        )
        is False
        and handoff.get(
            "operator_asserts_source_safe"
        )
        is False
        and handoff.get(
            "independent_source_review_required"
        )
        is True
        and handoff.get(
            "signed_source_attestation_required"
        )
        is True
        and handoff.get("next_gate")
        == "SIGNED_INDEPENDENT_ADAPTER_SOURCE_ATTESTATION_REQUIRED"
        and _permissions_false(handoff)
    )
    check(
        "handoff_ready_and_non_authorizing",
        handoff_ready,
    )

    request_safe = (
        request.get("request_schema_version") == 1
        and request.get("request_type")
        == REQUEST_TYPE
        and request.get("requested_control")
        == ATTESTATION_TYPE
        and request.get(
            "operator_asserts_source_safe"
        )
        is False
        and request.get(
            "requires_human_source_review"
        )
        is True
        and request.get(
            "signed_source_attestation_required"
        )
        is True
        and _permissions_false(request)
    )
    check(
        "review_request_non_authorizing",
        request_safe,
    )

    review_request_sha256 = (
        canonical_json_sha256(
            request
        )
    )
    handoff_request_sha256 = _sha256(
        handoff.get(
            "review_request_sha256"
        )
    )
    check(
        "review_request_digest_bound",
        review_request_sha256 is not None
        and handoff_request_sha256 is not None
        and review_request_sha256
        == handoff_request_sha256
        == _sha256(
            artifact.get(
                "review_request_sha256"
            )
        ),
    )

    source_review_digest = (
        canonical_json_sha256(
            source_review
        )
    )
    handoff_source_review_digest = _sha256(
        handoff.get(
            "source_review_artifact_sha256"
        )
    )
    check(
        "source_review_artifact_digest_bound",
        source_review_digest is not None
        and handoff_source_review_digest is not None
        and source_review_digest
        == handoff_source_review_digest
        == _sha256(
            artifact.get(
                "source_review_artifact_sha256"
            )
        )
        == _sha256(
            request.get(
                "source_review_artifact_sha256"
            )
        ),
    )

    source_review_safe = (
        source_review.get("engine")
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
        and source_review.get("g2_probe_stage")
        == "POST_REVIEW_PROBE"
        and _permissions_false(source_review)
    )
    check(
        "source_review_safe_and_non_authorizing",
        source_review_safe,
    )

    current_git_sha = _git_sha(
        current_git_sha
    )
    bound_git_sha = _git_sha(
        request.get("git_sha")
    )
    check(
        "git_sha_bound",
        current_git_sha is not None
        and bound_git_sha is not None
        and current_git_sha
        == bound_git_sha
        == _git_sha(
            source_review.get("git_sha")
        )
        == _git_sha(
            artifact.get("git_sha")
        ),
    )
    check(
        "repository_clean",
        repository_clean is True,
    )

    actual_source_sha256 = (
        hashlib.sha256(
            source_text.encode("utf-8")
        ).hexdigest()
        if isinstance(source_text, str)
        and source_text
        else None
    )
    source_sha256 = _sha256(
        request.get("source_sha256")
    )
    check(
        "source_sha256_bound",
        actual_source_sha256 is not None
        and source_sha256 is not None
        and actual_source_sha256
        == source_sha256
        == _sha256(
            source_review.get("source_sha256")
        )
        == _sha256(
            artifact.get("source_sha256")
        ),
    )

    binding_fields = (
        "runtime_prerequisite_sha256",
        "source_policy_sha256",
        "skeleton_version",
        "adapter_class",
    )
    check(
        "signed_source_identity_bound",
        all(
            artifact.get(name)
            == request.get(name)
            == source_review.get(name)
            for name in binding_fields
        )
        and _sha256(
            artifact.get(
                "runtime_prerequisite_sha256"
            )
        )
        is not None
        and _sha256(
            artifact.get(
                "source_policy_sha256"
            )
        )
        is not None
        and artifact.get(
            "skeleton_version"
        )
        == SKELETON_VERSION
        and artifact.get(
            "adapter_class"
        )
        == EXPECTED_CLASS,
    )

    check(
        "g2_probe_stage_bound",
        request.get("g2_probe_stage")
        == source_review.get("g2_probe_stage")
        == "POST_REVIEW_PROBE",
    )

    check(
        "runtime_provenance_fields_bound",
        request.get("authorization_id")
        == source_review.get("authorization_id")
        and request.get("evidence_run_id")
        == source_review.get("evidence_run_id")
        and request.get("gce_instance_id")
        == source_review.get("gce_instance_id")
        and request.get("g0_g1_proof_sha256")
        == source_review.get("g0_g1_proof_sha256")
        and request.get(
            "g2_paper_read_only_proof_sha256"
        )
        == source_review.get(
            "g2_paper_read_only_proof_sha256"
        )
        and request.get(
            "gateway_read_only_attestation_sha256"
        )
        == source_review.get(
            "gateway_read_only_attestation_sha256"
        )
        and _fingerprints(
            request.get(
                "paper_account_fingerprints"
            )
        )
        == _fingerprints(
            source_review.get(
                "paper_account_fingerprints"
            )
        )
        is not None,
    )

    failures = [
        name
        for name, passed in checks.items()
        if not passed
    ]
    if failures:
        return _blocked(
            "SIGNED_ADAPTER_SOURCE_ATTESTATION_INVALID",
            checks,
        )

    artifact_sha256 = canonical_json_sha256(
        artifact
    )
    if artifact_sha256 is None:
        return _blocked(
            "SOURCE_ATTESTATION_DIGEST_UNAVAILABLE",
            checks,
        )

    return {
        "engine": ENGINE_VERSION,
        "status": "VERIFIED",
        "verified": True,
        "adapter_source_independently_attested": True,
        "reason": "INDEPENDENT_SOURCE_REVIEW_ATTESTATION_VERIFIED",
        "checks": checks,
        "review_id": review_id,
        "reviewer_id": reviewer_id,
        "captured_at_utc": artifact.get(
            "captured_at_utc"
        ),
        "expires_at_utc": artifact.get(
            "expires_at_utc"
        ),
        "git_sha": current_git_sha,
        "source_review_artifact_sha256": (
            source_review_digest
        ),
        "review_request_sha256": (
            review_request_sha256
        ),
        "source_sha256": source_sha256,
        "source_policy_sha256": artifact.get(
            "source_policy_sha256"
        ),
        "source_attestation_sha256": (
            artifact_sha256
        ),
        "reviewer_evidence_sha256": (
            reviewer_evidence_sha256
        ),
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
            "NON_EXECUTABLE_ADAPTER_IMPLEMENTATION_DESIGN_REVIEW_REQUIRED"
        ),
    }
