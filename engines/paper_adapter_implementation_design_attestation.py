"""G8.18 verifier for independently signed adapter implementation-design review.

The verifier authenticates a human review of the exact G8.16 design handed off
by G8.17. A successful result advances review state only. It does not enable
implementation, broker connectivity, order materialization, or execution.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import re
from uuid import UUID

from engines.paper_adapter_implementation_design import (
    DESIGN_FIELDS,
    DESIGN_ID,
    DESIGN_NEXT_GATE,
    ENGINE_VERSION as DESIGN_ENGINE_VERSION,
    EXPECTED_METHODS,
    PERMISSION_FLAGS,
    SOURCE_NEXT_GATE,
    canonical_json_sha256,
)
from engines.paper_adapter_implementation_design_handoff import (
    ATTESTATION_TYPE,
    DESIGN_REVIEW_FIELDS,
    ENGINE_VERSION as HANDOFF_ENGINE_VERSION,
    REQUEST_TYPE,
    SIGNATURE_ALGORITHM,
)
from engines.paper_adapter_source_attestation import (
    decode_signature,
)
from engines.paper_adapter_source_review import (
    EXPECTED_CLASS,
    SKELETON_VERSION,
)


ENGINE_VERSION = "AURORA G8.18 Adapter Implementation Design Attestation Verifier"

ARTIFACT_FIELDS = {
    "schema_version",
    "attestation_type",
    "design_review_id",
    "decision",
    "reviewer_id",
    "captured_at_utc",
    "expires_at_utc",
    "design_review_artifact_sha256",
    "review_request_sha256",
    "design_sha256",
    "source_review_id",
    "source_git_sha",
    "source_sha256",
    "source_attestation_sha256",
    "design_id",
    "skeleton_version",
    "adapter_class",
    "reviewer_confirms_design_non_executable",
    "reviewer_confirms_fail_closed_defaults",
    "reviewer_confirms_no_credentials_or_raw_accounts",
    "reviewer_evidence_sha256",
    "signature_algorithm",
    "signature_b64",
}

POLICY_FIELDS = {
    "policy_version",
    "reviewer_id",
    "public_key_sha256",
    "expected_design_id",
    "expected_skeleton_version",
    "expected_adapter_class",
    "max_attestation_age_seconds",
    "allowed_clock_skew_seconds",
}

HANDOFF_FIELDS = {
    "engine",
    "request_type",
    "status",
    "reason",
    "ready_for_independent_design_review",
    "design_revalidated",
    "design_attestation_verified",
    "operator_asserts_design_safe",
    "design_review_artifact_sha256",
    "review_request_sha256",
    "review_request",
    "unsigned_attestation_template",
    "reviewer_must_set",
    "independent_design_review_required",
    "signed_design_attestation_required",
    *PERMISSION_FLAGS,
    "next_gate",
}

REQUEST_FIELDS = {
    "request_schema_version",
    "request_type",
    "requested_control",
    "generated_at_utc",
    "design_review_artifact_sha256",
    "design_sha256",
    "source_review_id",
    "source_git_sha",
    "source_sha256",
    "source_attestation_sha256",
    "design_id",
    "skeleton_version",
    "adapter_class",
    "operator_asserts_design_safe",
    "requires_human_design_review",
    "signed_design_attestation_required",
    *PERMISSION_FLAGS,
}

_HEX_40 = re.compile(r"^[0-9a-f]{40}$")
_HEX_64 = re.compile(r"^[0-9a-f]{64}$")
_REVIEWER_ID = re.compile(r"^[A-Za-z0-9._@+-]{3,128}$")


def canonical_signed_payload(artifact):
    if not isinstance(artifact, dict):
        return None
    payload = {
        key: value
        for key, value in artifact.items()
        if key != "signature_b64"
    }
    try:
        import json
        return json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, OverflowError):
        return None


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


def _blocked(reason, checks=None):
    return {
        "engine": ENGINE_VERSION,
        "status": "BLOCKED",
        "verified": False,
        "adapter_design_independently_attested": False,
        "reason": reason,
        "checks": checks or {},
        "design_review_id": None,
        "reviewer_id": None,
        "captured_at_utc": None,
        "expires_at_utc": None,
        "design_review_artifact_sha256": None,
        "review_request_sha256": None,
        "design_sha256": None,
        "source_review_id": None,
        "source_git_sha": None,
        "source_sha256": None,
        "source_attestation_sha256": None,
        "design_attestation_sha256": None,
        "reviewer_evidence_sha256": None,
        **{
            name: False
            for name in PERMISSION_FLAGS
        },
        "next_gate": "REPAIR_SIGNED_ADAPTER_IMPLEMENTATION_DESIGN_ATTESTATION",
    }


def _design_policy_safe(design):
    return (
        isinstance(design, dict)
        and set(design) == DESIGN_FIELDS
        and design.get("schema_version") == 1
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
        and design.get(
            "requires_independent_design_review"
        )
        is True
        and design.get(
            "signed_design_attestation_required"
        )
        is True
        and design.get("next_gate") == DESIGN_NEXT_GATE
        and _permissions_false(design)
    )


def evaluate_design_attestation(
    artifact,
    policy,
    public_key_bytes,
    signature_valid,
    handoff,
    design_review,
    design,
    source_text,
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
    design_review_ok = isinstance(design_review, dict)
    design_ok = isinstance(design, dict)

    check("artifact_is_object", artifact_ok)
    check("policy_is_object", policy_ok)
    check("handoff_is_object", handoff_ok)
    check("design_review_is_object", design_review_ok)
    check("design_is_object", design_ok)

    artifact = artifact if artifact_ok else {}
    policy = policy if policy_ok else {}
    handoff = handoff if handoff_ok else {}
    design_review = (
        design_review if design_review_ok else {}
    )
    design = design if design_ok else {}

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
        "design_review_field_set_exact",
        set(design_review) == DESIGN_REVIEW_FIELDS,
    )
    check(
        "design_field_set_exact",
        set(design) == DESIGN_FIELDS,
    )

    request = (
        handoff.get("review_request")
        if isinstance(
            handoff.get("review_request"),
            dict,
        )
        else {}
    )
    template = (
        handoff.get("unsigned_attestation_template")
        if isinstance(
            handoff.get("unsigned_attestation_template"),
            dict,
        )
        else {}
    )
    check(
        "review_request_field_set_exact",
        set(request) == REQUEST_FIELDS,
    )
    check(
        "unsigned_template_field_set_exact",
        set(template) == ARTIFACT_FIELDS,
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
    design_review_id = _uuid4(
        artifact.get("design_review_id")
    )
    check(
        "design_review_id_uuid4",
        design_review_id is not None,
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
        "policy_design_id",
        policy.get("expected_design_id")
        == DESIGN_ID,
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
    check("policy_max_age_valid", max_age_valid)
    check("policy_clock_skew_valid", clock_skew_valid)

    captured = _utc_datetime(
        artifact.get("captured_at_utc")
    )
    expires = _utc_datetime(
        artifact.get("expires_at_utc")
    )
    check("captured_at_valid", captured is not None)
    check("expires_at_valid", expires is not None)

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

    for field in (
        "reviewer_confirms_design_non_executable",
        "reviewer_confirms_fail_closed_defaults",
        "reviewer_confirms_no_credentials_or_raw_accounts",
    ):
        check(
            field,
            artifact.get(field) is True,
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

    handoff_safe = (
        handoff.get("engine")
        == HANDOFF_ENGINE_VERSION
        and handoff.get("request_type")
        == REQUEST_TYPE
        and handoff.get("status")
        == "READY_FOR_INDEPENDENT_IMPLEMENTATION_DESIGN_REVIEW"
        and handoff.get("reason")
        == "HUMAN_IMPLEMENTATION_DESIGN_REVIEW_REQUIRED"
        and handoff.get(
            "ready_for_independent_design_review"
        )
        is True
        and handoff.get("design_revalidated") is True
        and handoff.get(
            "design_attestation_verified"
        )
        is False
        and handoff.get(
            "operator_asserts_design_safe"
        )
        is False
        and handoff.get(
            "independent_design_review_required"
        )
        is True
        and handoff.get(
            "signed_design_attestation_required"
        )
        is True
        and handoff.get("next_gate")
        == "SIGNED_INDEPENDENT_ADAPTER_IMPLEMENTATION_DESIGN_ATTESTATION_REQUIRED"
        and _permissions_false(handoff)
    )
    check(
        "handoff_ready_and_non_authorizing",
        handoff_safe,
    )

    request_safe = (
        request.get("request_schema_version") == 1
        and request.get("request_type")
        == REQUEST_TYPE
        and request.get("requested_control")
        == ATTESTATION_TYPE
        and request.get(
            "operator_asserts_design_safe"
        )
        is False
        and request.get(
            "requires_human_design_review"
        )
        is True
        and request.get(
            "signed_design_attestation_required"
        )
        is True
        and _permissions_false(request)
    )
    check(
        "review_request_non_authorizing",
        request_safe,
    )

    template_safe = (
        template.get("schema_version") == 1
        and template.get("attestation_type")
        == ATTESTATION_TYPE
        and template.get("decision")
        == "REVIEW_REQUIRED"
        and template.get("design_review_id") is None
        and template.get("reviewer_id") is None
        and template.get("captured_at_utc") is None
        and template.get("expires_at_utc") is None
        and template.get(
            "reviewer_confirms_design_non_executable"
        )
        is None
        and template.get(
            "reviewer_confirms_fail_closed_defaults"
        )
        is None
        and template.get(
            "reviewer_confirms_no_credentials_or_raw_accounts"
        )
        is None
        and template.get("reviewer_evidence_sha256")
        is None
        and template.get("signature_algorithm")
        == SIGNATURE_ALGORITHM
        and template.get("signature_b64") is None
    )
    check(
        "unsigned_template_non_attesting",
        template_safe,
    )

    review_request_sha256 = (
        canonical_json_sha256(
            request
        )
    )
    check(
        "review_request_digest_bound",
        review_request_sha256 is not None
        and review_request_sha256
        == _sha256(
            handoff.get(
                "review_request_sha256"
            )
        )
        == _sha256(
            artifact.get(
                "review_request_sha256"
            )
        ),
    )

    design_review_sha256 = (
        canonical_json_sha256(
            design_review
        )
    )
    check(
        "design_review_artifact_digest_bound",
        design_review_sha256 is not None
        and design_review_sha256
        == _sha256(
            handoff.get(
                "design_review_artifact_sha256"
            )
        )
        == _sha256(
            request.get(
                "design_review_artifact_sha256"
            )
        )
        == _sha256(
            artifact.get(
                "design_review_artifact_sha256"
            )
        ),
    )

    design_review_safe = (
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
    )
    check(
        "design_review_safe_and_non_authorizing",
        design_review_safe,
    )

    check(
        "design_policy_safe",
        _design_policy_safe(
            design
        ),
    )
    design_sha256 = canonical_json_sha256(
        design
    )
    check(
        "design_digest_bound",
        design_sha256 is not None
        and design_sha256
        == _sha256(
            design_review.get(
                "design_sha256"
            )
        )
        == _sha256(
            request.get(
                "design_sha256"
            )
        )
        == _sha256(
            artifact.get(
                "design_sha256"
            )
        ),
    )

    actual_source_sha256 = (
        hashlib.sha256(
            source_text.encode("utf-8")
        ).hexdigest()
        if isinstance(source_text, str)
        and source_text
        else None
    )
    source_review_id = _uuid4(
        design_review.get(
            "source_review_id"
        )
    )
    source_git_sha = _git_sha(
        design_review.get(
            "source_git_sha"
        )
    )
    source_sha256 = _sha256(
        design_review.get(
            "source_sha256"
        )
    )
    source_attestation_sha256 = _sha256(
        design_review.get(
            "source_attestation_sha256"
        )
    )

    check(
        "source_identity_bound",
        source_review_id is not None
        and source_git_sha is not None
        and source_sha256 is not None
        and actual_source_sha256 is not None
        and source_sha256 == actual_source_sha256
        and source_review_id
        == _uuid4(
            request.get(
                "source_review_id"
            )
        )
        == _uuid4(
            artifact.get(
                "source_review_id"
            )
        )
        and source_git_sha
        == _git_sha(
            request.get(
                "source_git_sha"
            )
        )
        == _git_sha(
            artifact.get(
                "source_git_sha"
            )
        )
        and source_sha256
        == _sha256(
            request.get(
                "source_sha256"
            )
        )
        == _sha256(
            artifact.get(
                "source_sha256"
            )
        )
        and source_attestation_sha256 is not None
        and source_attestation_sha256
        == _sha256(
            request.get(
                "source_attestation_sha256"
            )
        )
        == _sha256(
            artifact.get(
                "source_attestation_sha256"
            )
        ),
    )

    check(
        "design_identity_bound",
        artifact.get("design_id")
        == request.get("design_id")
        == design.get("design_id")
        == DESIGN_ID
        and artifact.get("skeleton_version")
        == request.get("skeleton_version")
        == design.get("skeleton_version")
        == SKELETON_VERSION
        and artifact.get("adapter_class")
        == request.get("adapter_class")
        == design.get("adapter_class")
        == EXPECTED_CLASS,
    )

    check(
        "repository_clean",
        repository_clean is True,
    )

    failures = [
        name
        for name, passed in checks.items()
        if not passed
    ]
    if failures:
        return _blocked(
            "SIGNED_ADAPTER_IMPLEMENTATION_DESIGN_ATTESTATION_INVALID",
            checks,
        )

    design_attestation_sha256 = (
        canonical_json_sha256(
            artifact
        )
    )
    if design_attestation_sha256 is None:
        return _blocked(
            "DESIGN_ATTESTATION_DIGEST_UNAVAILABLE",
            checks,
        )

    return {
        "engine": ENGINE_VERSION,
        "status": "VERIFIED",
        "verified": True,
        "adapter_design_independently_attested": True,
        "reason": "INDEPENDENT_IMPLEMENTATION_DESIGN_ATTESTATION_VERIFIED",
        "checks": checks,
        "design_review_id": design_review_id,
        "reviewer_id": reviewer_id,
        "captured_at_utc": artifact.get(
            "captured_at_utc"
        ),
        "expires_at_utc": artifact.get(
            "expires_at_utc"
        ),
        "design_review_artifact_sha256": (
            design_review_sha256
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
        "design_attestation_sha256": (
            design_attestation_sha256
        ),
        "reviewer_evidence_sha256": (
            reviewer_evidence_sha256
        ),
        **{
            name: False
            for name in PERMISSION_FLAGS
        },
        "next_gate": (
            "NON_EXECUTABLE_ADAPTER_IMPLEMENTATION_CANDIDATE_REQUIRED"
        ),
    }
