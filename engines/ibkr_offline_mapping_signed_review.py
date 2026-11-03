"""G8.33: independent signed offline IBKR mapping review verification.

No self-signing; verification changes review state only. All execution gates stay shut.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import re

from engines.ibkr_offline_mapping_review_handoff import (
    ENGINE_VERSION as HANDOFF_ENGINE,
    NEXT_GATE as HANDOFF_NEXT_GATE,
    REQUEST_TYPE, ATTESTATION_TYPE,
    create_offline_mapping_review_handoff,
)
from engines.ibkr_offline_order_object_mapping import _digest
from engines.ibkr_order_object_design_attestation import _date, _uuid
from engines.paper_adapter_source_attestation import decode_signature
from engines.paper_adapter_implementation_candidate_review import PERMISSION_FLAGS

ENGINE_VERSION = "AURORA G8.33 Signed Offline IBKR Mapping Review"
NEXT_GATE = "OFFLINE_IBKR_MAPPING_POST_ATTESTATION_RESEARCH_REQUIRED"
HEX = re.compile(r"^[0-9a-f]{64}$")
REVIEWER = re.compile(r"^[A-Za-z0-9._@+-]{3,128}$")

BIND_FIELDS = (
    "review_request_sha256",
    "design_sha256",
    "signed_candidate_attestation_sha256",
    "candidate_attestation_result_sha256",
    "normalized_preview_sha256",
    "mapping_result_sha256",
    "mapping_sha256",
)
CONFIRM_FIELDS = (
    "reviewer_confirms_paper_only",
    "reviewer_confirms_no_broker_objects",
    "reviewer_confirms_no_network_or_submission",
    "reviewer_confirms_transmit_false",
    "reviewer_confirms_preview_attestation_bound",
)
ARTIFACT_FIELDS = {
    "schema_version", "attestation_type", "decision", "review_id",
    "reviewer_id", "captured_at_utc", "expires_at_utc",
    *BIND_FIELDS, *CONFIRM_FIELDS,
    "reviewer_evidence_sha256", "signature_algorithm", "signature_b64",
}
POLICY_FIELDS = {
    "policy_version", "reviewer_id", "public_key_sha256",
    "expected_request_type", "max_attestation_age_seconds",
    "allowed_clock_skew_seconds",
}
HANDOFF_FIELDS = {
    "engine", "status", "reason", "ready_for_independent_review",
    "mapping_revalidated", "operator_approves_execution",
    "review_request_sha256", "review_request",
    "unsigned_attestation_template", *PERMISSION_FLAGS, "next_gate",
}

def canonical_signed_payload(artifact):
    if not isinstance(artifact, dict):
        return None
    try:
        return json.dumps(
            {k: v for k, v in artifact.items() if k != "signature_b64"},
            sort_keys=True, separators=(",", ":"), ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, OverflowError):
        return None

def _hex(value):
    return isinstance(value, str) and HEX.fullmatch(value) is not None

def _closed(value):
    return isinstance(value, dict) and all(
        value.get(flag) is False for flag in PERMISSION_FLAGS
    )

def _blocked(checks):
    return {
        "engine": ENGINE_VERSION, "status": "BLOCKED", "verified": False,
        "offline_mapping_independently_attested": False,
        "reason": "SIGNED_OFFLINE_MAPPING_REVIEW_INVALID",
        "checks": checks, "review_id": None, "reviewer_id": None,
        "review_request_sha256": None, "mapping_sha256": None,
        "attestation_sha256": None,
        **{flag: False for flag in PERMISSION_FLAGS},
        "next_gate": "REPAIR_SIGNED_OFFLINE_MAPPING_REVIEW",
    }

def evaluate_signed_offline_mapping_review(
    artifact, policy, public_key_bytes, signature_valid,
    handoff, design, candidate_attestation, normalized_preview,
    mapping_result, repository_clean, *, now=None,
):
    if now is None:
        now = datetime.now(timezone.utc)
    checks = {}
    def check(name, value):
        checks[name] = value is True

    artifact = artifact if isinstance(artifact, dict) else {}
    policy = policy if isinstance(policy, dict) else {}
    handoff = handoff if isinstance(handoff, dict) else {}
    request = handoff.get("review_request")
    template = handoff.get("unsigned_attestation_template")

    check("artifact_exact_schema", set(artifact) == ARTIFACT_FIELDS)
    check("policy_exact_schema", set(policy) == POLICY_FIELDS)
    check("artifact_identity",
          type(artifact.get("schema_version")) is int
          and artifact.get("schema_version") == 1
          and artifact.get("attestation_type") == ATTESTATION_TYPE
          and artifact.get("decision") == "ATTESTED"
          and artifact.get("signature_algorithm") == "ED25519")
    check("review_id_uuid4", _uuid(artifact.get("review_id")) is not None)
    reviewer_id = artifact.get("reviewer_id")
    check("reviewer_policy_identity",
          isinstance(reviewer_id, str)
          and REVIEWER.fullmatch(reviewer_id) is not None
          and reviewer_id == policy.get("reviewer_id"))
    check("signature_encoding", decode_signature(artifact.get("signature_b64")) is not None)
    check("independent_signature_verified", signature_valid is True)
    check("policy_identity",
          type(policy.get("policy_version")) is int
          and policy.get("policy_version") == 1
          and policy.get("expected_request_type") == REQUEST_TYPE)
    key_valid = (
        isinstance(public_key_bytes, bytes)
        and public_key_bytes.startswith(b"-----BEGIN PUBLIC KEY-----")
        and b"PRIVATE KEY" not in public_key_bytes
    )
    key_hash = hashlib.sha256(public_key_bytes).hexdigest() if isinstance(public_key_bytes, bytes) else None
    check("trusted_public_key_bound",
          key_valid and _hex(policy.get("public_key_sha256"))
          and policy.get("public_key_sha256") == key_hash)

    max_age = policy.get("max_attestation_age_seconds")
    skew = policy.get("allowed_clock_skew_seconds")
    valid_time_policy = (
        type(max_age) is int and 60 <= max_age <= 86400
        and type(skew) is int and 0 <= skew <= 300
    )
    check("time_policy", valid_time_policy)
    captured = _date(artifact.get("captured_at_utc"))
    expires = _date(artifact.get("expires_at_utc"))
    generated = _date(request.get("generated_at_utc")) if isinstance(request, dict) else None
    fresh = (
        isinstance(now, datetime) and now.tzinfo is not None
        and valid_time_policy and captured is not None and expires is not None
        and generated is not None and generated <= captured < expires
        and (captured - generated).total_seconds() <= max_age
        and (captured - now).total_seconds() <= skew
        and (now - captured).total_seconds() <= max_age
        and (expires - captured).total_seconds() <= max_age
        and now <= expires
    )
    check("review_and_request_fresh", fresh)
    for flag in CONFIRM_FIELDS:
        check(flag, artifact.get(flag) is True)
    digest = artifact.get("reviewer_evidence_sha256")
    check("reviewer_evidence_hash", _hex(digest) and digest != "0"*64)
    check("repository_clean", repository_clean is True)

    check("handoff_exact_schema", set(handoff) == HANDOFF_FIELDS)
    check("handoff_review_only",
          handoff.get("engine") == HANDOFF_ENGINE
          and handoff.get("status") == "READY_FOR_INDEPENDENT_OFFLINE_MAPPING_REVIEW"
          and handoff.get("reason") == "SIGNED_INDEPENDENT_MAPPING_REVIEW_REQUIRED"
          and handoff.get("ready_for_independent_review") is True
          and handoff.get("mapping_revalidated") is True
          and handoff.get("operator_approves_execution") is False
          and handoff.get("next_gate") == HANDOFF_NEXT_GATE
          and _closed(handoff))
    request_ok = isinstance(request, dict)
    check("request_review_only",
          request_ok
          and type(request.get("schema_version")) is int
          and request.get("schema_version") == 1
          and request.get("request_type") == REQUEST_TYPE
          and request.get("requested_control") == ATTESTATION_TYPE
          and request.get("independent_human_review_required") is True
          and request.get("operator_approves_execution") is False
          and all(request.get(flag) is False for flag in (
              "broker_contract_created", "broker_order_created",
              "network_accessed", "transmit"))
          and _closed(request))
    check("unsigned_template_exact_schema",
          isinstance(template, dict)
          and set(template) == ARTIFACT_FIELDS
          and template.get("decision") == "REVIEW_REQUIRED"
          and template.get("signature_algorithm") == "ED25519"
          and template.get("signature_b64") is None
          and template.get("review_id") is None
          and template.get("reviewer_id") is None
          and all(template.get(flag) is None for flag in CONFIRM_FIELDS))

    try:
        rebuilt = create_offline_mapping_review_handoff(
            design, candidate_attestation, normalized_preview, mapping_result,
            now=generated if generated is not None else now,
        )
        request_sha = _digest(request)
        expected = {
            "review_request_sha256": request_sha,
            "design_sha256": _digest(design),
            "signed_candidate_attestation_sha256": candidate_attestation.get("attestation_sha256"),
            "candidate_attestation_result_sha256": _digest(candidate_attestation),
            "normalized_preview_sha256": _digest(normalized_preview),
            "mapping_result_sha256": _digest(mapping_result),
            "mapping_sha256": mapping_result.get("mapping_sha256"),
        }
    except (TypeError, ValueError, OverflowError, AttributeError, UnicodeError):
        rebuilt = None
        request_sha = None
        expected = {}
    check("handoff_reproducible",
          isinstance(rebuilt, dict)
          and rebuilt.get("ready_for_independent_review") is True
          and rebuilt == handoff)
    check("request_digest_bound",
          _hex(request_sha) and handoff.get("review_request_sha256") == request_sha)
    check("attestation_all_hashes_bound",
          len(expected) == len(BIND_FIELDS)
          and all(_hex(expected.get(field))
                  and artifact.get(field) == expected[field]
                  and (field == "review_request_sha256" or request.get(field) == expected[field])
                  for field in BIND_FIELDS)
          if request_ok else False)
    check("unsigned_template_hashes_bound",
          isinstance(template, dict)
          and all(_hex(expected.get(field))
                  and template.get(field) == expected[field]
                  for field in BIND_FIELDS))
    if not all(checks.values()):
        return _blocked(checks)
    return {
        "engine": ENGINE_VERSION, "status": "VERIFIED", "verified": True,
        "offline_mapping_independently_attested": True,
        "reason": "INDEPENDENT_OFFLINE_MAPPING_ATTESTATION_VERIFIED",
        "checks": checks, "review_id": artifact["review_id"],
        "reviewer_id": reviewer_id,
        "review_request_sha256": request_sha,
        "mapping_sha256": expected["mapping_sha256"],
        "attestation_sha256": _digest(artifact),
        **{flag: False for flag in PERMISSION_FLAGS},
        "next_gate": NEXT_GATE,
    }
