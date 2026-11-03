"""G8.24 signed independent offline materializer attestation verifier."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import re
from uuid import UUID

from engines.offline_order_request_materializer_handoff import (
    ATTESTATION_TYPE,
    ENGINE_VERSION as HANDOFF_ENGINE_VERSION,
    NEXT_GATE as HANDOFF_NEXT_GATE,
    REQUEST_TYPE,
    SIGNATURE_ALGORITHM,
    _validate_design,
    _validate_source,
    canonical_json_sha256,
)
from engines.paper_adapter_implementation_candidate_review import PERMISSION_FLAGS
from engines.paper_adapter_source_attestation import decode_signature


ENGINE_VERSION = "AURORA G8.24 Offline Materializer Attestation Verifier"
NEXT_GATE = "IBKR_ORDER_OBJECT_MATERIALIZER_DESIGN_REQUIRED"

ARTIFACT_FIELDS = {
    "schema_version",
    "attestation_type",
    "materializer_review_id",
    "decision",
    "reviewer_id",
    "captured_at_utc",
    "expires_at_utc",
    "review_request_sha256",
    "design_sha256",
    "materializer_source_sha256",
    "cli_source_sha256",
    "reviewer_confirms_offline_only",
    "reviewer_confirms_no_broker_imports",
    "reviewer_confirms_no_network_path",
    "reviewer_confirms_fail_closed_intent_schema",
    "reviewer_evidence_sha256",
    "signature_algorithm",
    "signature_b64",
}

POLICY_FIELDS = {
    "policy_version",
    "reviewer_id",
    "public_key_sha256",
    "expected_design_id",
    "max_attestation_age_seconds",
    "allowed_clock_skew_seconds",
}

HANDOFF_FIELDS = {
    "engine",
    "request_type",
    "status",
    "reason",
    "ready_for_independent_materializer_review",
    "design_revalidated",
    "materializer_source_revalidated",
    "cli_source_revalidated",
    "operator_asserts_materializer_safe",
    "design_sha256",
    "materializer_source_sha256",
    "cli_source_sha256",
    "review_request_sha256",
    "review_request",
    "unsigned_attestation_template",
    "reviewer_must_set",
    "independent_materializer_review_required",
    "signed_materializer_attestation_required",
    *PERMISSION_FLAGS,
    "next_gate",
}

REQUEST_FIELDS = {
    "request_schema_version",
    "request_type",
    "requested_control",
    "generated_at_utc",
    "design_sha256",
    "materializer_source_sha256",
    "cli_source_sha256",
    "operator_asserts_materializer_safe",
    "requires_human_materializer_review",
    "signed_materializer_attestation_required",
    *PERMISSION_FLAGS,
}

_HEX_64 = re.compile(r"^[0-9a-f]{64}$")
_REVIEWER_ID = re.compile(r"^[A-Za-z0-9._@+-]{3,128}$")
EXPECTED_DESIGN_ID = "AURORA_G8_22_OFFLINE_ORDER_REQUEST_MATERIALIZER_DESIGN_V1"


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


def _blocked(reason, checks=None):
    return {
        "engine": ENGINE_VERSION,
        "status": "BLOCKED",
        "verified": False,
        "offline_materializer_independently_attested": False,
        "reason": reason,
        "checks": checks or {},
        "materializer_review_id": None,
        "reviewer_id": None,
        "captured_at_utc": None,
        "expires_at_utc": None,
        "review_request_sha256": None,
        "design_sha256": None,
        "materializer_source_sha256": None,
        "cli_source_sha256": None,
        "materializer_attestation_sha256": None,
        "reviewer_evidence_sha256": None,
        **{name: False for name in PERMISSION_FLAGS},
        "next_gate": "REPAIR_SIGNED_OFFLINE_MATERIALIZER_ATTESTATION",
    }


def evaluate_materializer_attestation(
    artifact,
    policy,
    public_key_bytes,
    signature_valid,
    handoff,
    design,
    materializer_source,
    cli_source,
    repository_clean,
    now=None,
):
    now = (
        now.astimezone(timezone.utc)
        if isinstance(now, datetime) and now.tzinfo is not None
        else datetime.now(timezone.utc)
    )
    checks = {}

    def check(name, condition):
        checks[name] = bool(condition)

    artifact = artifact if isinstance(artifact, dict) else {}
    policy = policy if isinstance(policy, dict) else {}
    handoff = handoff if isinstance(handoff, dict) else {}
    design = design if isinstance(design, dict) else {}

    check("artifact_field_set_exact", set(artifact) == ARTIFACT_FIELDS)
    check("policy_field_set_exact", set(policy) == POLICY_FIELDS)
    check("handoff_field_set_exact", set(handoff) == HANDOFF_FIELDS)

    request = (
        handoff.get("review_request")
        if isinstance(handoff.get("review_request"), dict)
        else {}
    )
    template = (
        handoff.get("unsigned_attestation_template")
        if isinstance(handoff.get("unsigned_attestation_template"), dict)
        else {}
    )
    check("review_request_field_set_exact", set(request) == REQUEST_FIELDS)
    check("unsigned_template_field_set_exact", set(template) == ARTIFACT_FIELDS)

    check(
        "artifact_identity",
        artifact.get("schema_version") == 1
        and artifact.get("attestation_type") == ATTESTATION_TYPE
        and artifact.get("decision") == "ATTESTED"
        and artifact.get("signature_algorithm") == SIGNATURE_ALGORITHM,
    )
    materializer_review_id = _uuid4(artifact.get("materializer_review_id"))
    check("materializer_review_id_uuid4", materializer_review_id is not None)
    check(
        "signature_encoding_valid",
        decode_signature(artifact.get("signature_b64")) is not None,
    )
    check("ed25519_signature_valid", signature_valid is True)

    reviewer_id = str(artifact.get("reviewer_id") or "").strip()
    policy_reviewer_id = str(policy.get("reviewer_id") or "").strip()
    check("policy_version", policy.get("policy_version") == 1)
    check("reviewer_id_format", bool(_REVIEWER_ID.fullmatch(reviewer_id)))
    check(
        "reviewer_matches_policy",
        bool(reviewer_id) and reviewer_id == policy_reviewer_id,
    )
    check(
        "policy_expected_design_id",
        policy.get("expected_design_id") == EXPECTED_DESIGN_ID,
    )

    public_key_valid = (
        isinstance(public_key_bytes, bytes)
        and b"-----BEGIN PUBLIC KEY-----" in public_key_bytes
        and b"PRIVATE KEY" not in public_key_bytes
    )
    public_key_sha256 = (
        hashlib.sha256(public_key_bytes).hexdigest()
        if isinstance(public_key_bytes, bytes)
        else ""
    )
    policy_key_sha256 = _sha256(policy.get("public_key_sha256"))
    check("reviewer_public_key_material_valid", public_key_valid)
    check(
        "policy_public_key_sha256_valid",
        policy_key_sha256 is not None and policy_key_sha256 != ("0" * 64),
    )
    check(
        "public_key_matches_policy",
        public_key_valid and policy_key_sha256 == public_key_sha256,
    )

    max_age = policy.get("max_attestation_age_seconds")
    skew = policy.get("allowed_clock_skew_seconds")
    max_age_valid = type(max_age) is int and 60 <= max_age <= 86400
    skew_valid = type(skew) is int and 0 <= skew <= 300
    check("policy_max_age_valid", max_age_valid)
    check("policy_clock_skew_valid", skew_valid)

    captured = _utc_datetime(artifact.get("captured_at_utc"))
    expires = _utc_datetime(artifact.get("expires_at_utc"))
    check("captured_at_valid", captured is not None)
    check("expires_at_valid", expires is not None)

    if captured is not None and expires is not None and max_age_valid and skew_valid:
        age = (now - captured).total_seconds()
        validity = (expires - captured).total_seconds()
        check("capture_not_in_future", age >= -skew)
        check("attestation_not_expired", now <= expires)
        check("attestation_age_within_policy", age <= max_age)
        check("attestation_validity_window_positive", validity > 0)
        check("attestation_validity_window_within_policy", validity <= max_age)
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
        "reviewer_confirms_offline_only",
        "reviewer_confirms_no_broker_imports",
        "reviewer_confirms_no_network_path",
        "reviewer_confirms_fail_closed_intent_schema",
    ):
        check(field, artifact.get(field) is True)

    reviewer_evidence_sha256 = _sha256(
        artifact.get("reviewer_evidence_sha256")
    )
    check(
        "reviewer_evidence_sha256_valid",
        reviewer_evidence_sha256 is not None
        and reviewer_evidence_sha256 != ("0" * 64),
    )

    handoff_safe = (
        handoff.get("engine") == HANDOFF_ENGINE_VERSION
        and handoff.get("request_type") == REQUEST_TYPE
        and handoff.get("status")
        == "READY_FOR_INDEPENDENT_OFFLINE_MATERIALIZER_REVIEW"
        and handoff.get("reason")
        == "HUMAN_OFFLINE_MATERIALIZER_REVIEW_REQUIRED"
        and handoff.get("ready_for_independent_materializer_review") is True
        and handoff.get("design_revalidated") is True
        and handoff.get("materializer_source_revalidated") is True
        and handoff.get("cli_source_revalidated") is True
        and handoff.get("operator_asserts_materializer_safe") is False
        and handoff.get("independent_materializer_review_required") is True
        and handoff.get("signed_materializer_attestation_required") is True
        and handoff.get("next_gate") == HANDOFF_NEXT_GATE
        and _permissions_false(handoff)
    )
    check("handoff_ready_and_non_authorizing", handoff_safe)

    request_safe = (
        request.get("request_schema_version") == 1
        and request.get("request_type") == REQUEST_TYPE
        and request.get("requested_control") == ATTESTATION_TYPE
        and request.get("operator_asserts_materializer_safe") is False
        and request.get("requires_human_materializer_review") is True
        and request.get("signed_materializer_attestation_required") is True
        and _permissions_false(request)
    )
    check("review_request_non_authorizing", request_safe)

    template_safe = (
        template.get("schema_version") == 1
        and template.get("attestation_type") == ATTESTATION_TYPE
        and template.get("decision") == "REVIEW_REQUIRED"
        and template.get("materializer_review_id") is None
        and template.get("reviewer_id") is None
        and template.get("signature_b64") is None
        and template.get("reviewer_confirms_offline_only") is None
        and template.get("reviewer_confirms_no_broker_imports") is None
        and template.get("reviewer_confirms_no_network_path") is None
        and template.get("reviewer_confirms_fail_closed_intent_schema") is None
    )
    check("unsigned_template_non_attesting", template_safe)

    review_request_sha256 = canonical_json_sha256(request)
    check(
        "review_request_digest_bound",
        review_request_sha256 is not None
        and review_request_sha256
        == _sha256(handoff.get("review_request_sha256"))
        == _sha256(artifact.get("review_request_sha256")),
    )

    design_valid = _validate_design(design)
    actual_design_sha256 = canonical_json_sha256(design)
    design_sha256 = _sha256(handoff.get("design_sha256"))
    check(
        "design_policy_and_digest_bound",
        design_valid is True
        and design.get("design_id") == EXPECTED_DESIGN_ID
        and actual_design_sha256 is not None
        and design_sha256 == actual_design_sha256
        == _sha256(request.get("design_sha256"))
        == _sha256(artifact.get("design_sha256")),
    )

    materializer_valid, _ = _validate_source(
        materializer_source,
        materializer=True,
    )
    actual_materializer_sha256 = (
        hashlib.sha256(materializer_source.encode("utf-8")).hexdigest()
        if isinstance(materializer_source, str) and materializer_source
        else None
    )
    materializer_source_sha256 = _sha256(
        handoff.get("materializer_source_sha256")
    )
    check(
        "materializer_source_policy_and_digest_bound",
        materializer_valid is True
        and actual_materializer_sha256 is not None
        and materializer_source_sha256 == actual_materializer_sha256
        == _sha256(request.get("materializer_source_sha256"))
        == _sha256(artifact.get("materializer_source_sha256")),
    )

    cli_valid, _ = _validate_source(cli_source, materializer=False)
    actual_cli_sha256 = (
        hashlib.sha256(cli_source.encode("utf-8")).hexdigest()
        if isinstance(cli_source, str) and cli_source
        else None
    )
    cli_source_sha256 = _sha256(handoff.get("cli_source_sha256"))
    check(
        "cli_source_policy_and_digest_bound",
        cli_valid is True
        and actual_cli_sha256 is not None
        and cli_source_sha256 == actual_cli_sha256
        == _sha256(request.get("cli_source_sha256"))
        == _sha256(artifact.get("cli_source_sha256")),
    )

    check("repository_clean", repository_clean is True)

    failures = [name for name, passed in checks.items() if not passed]
    if failures:
        return _blocked(
            "SIGNED_OFFLINE_MATERIALIZER_ATTESTATION_INVALID",
            checks,
        )

    materializer_attestation_sha256 = canonical_json_sha256(artifact)
    if materializer_attestation_sha256 is None:
        return _blocked("MATERIALIZER_ATTESTATION_DIGEST_UNAVAILABLE", checks)

    return {
        "engine": ENGINE_VERSION,
        "status": "VERIFIED",
        "verified": True,
        "offline_materializer_independently_attested": True,
        "reason": "INDEPENDENT_OFFLINE_MATERIALIZER_ATTESTATION_VERIFIED",
        "checks": checks,
        "materializer_review_id": materializer_review_id,
        "reviewer_id": reviewer_id,
        "captured_at_utc": artifact.get("captured_at_utc"),
        "expires_at_utc": artifact.get("expires_at_utc"),
        "review_request_sha256": review_request_sha256,
        "design_sha256": design_sha256,
        "materializer_source_sha256": materializer_source_sha256,
        "cli_source_sha256": cli_source_sha256,
        "materializer_attestation_sha256": materializer_attestation_sha256,
        "reviewer_evidence_sha256": reviewer_evidence_sha256,
        **{name: False for name in PERMISSION_FLAGS},
        "next_gate": NEXT_GATE,
    }
