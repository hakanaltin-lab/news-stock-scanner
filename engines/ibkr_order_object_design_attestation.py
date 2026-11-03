"""G8.27: independent signed G8.25 Order-object design attestation.

Review verification only. No IBKR imports, networking, order objects or orders.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import re
from uuid import UUID

from engines.ibkr_order_object_design_handoff import (
    ATTESTATION_TYPE, ENGINE_VERSION as HANDOFF_ENGINE, NEXT_GATE as HANDOFF_NEXT_GATE,
    REQUEST_TYPE, _digest, evaluate_order_object_design_handoff,
)
from engines.paper_adapter_implementation_candidate_review import PERMISSION_FLAGS
from engines.paper_adapter_source_attestation import decode_signature

ENGINE_VERSION = "AURORA G8.27 Signed IBKR Order Object Design Attestation"
NEXT_GATE = "NON_EXECUTABLE_IBKR_ORDER_OBJECT_IMPLEMENTATION_CANDIDATE_REQUIRED"
HEX64 = re.compile(r"^[0-9a-f]{64}$")
REVIEWER = re.compile(r"^[A-Za-z0-9._@+-]{3,128}$")
ARTIFACT_FIELDS = {
    "schema_version", "attestation_type", "decision", "review_id",
    "reviewer_id", "captured_at_utc", "expires_at_utc",
    "review_request_sha256", "design_sha256",
    "upstream_attestation_result_sha256",
    "reviewer_confirms_design_only", "reviewer_confirms_no_broker_objects",
    "reviewer_confirms_paper_only", "reviewer_confirms_transmit_false",
    "reviewer_evidence_sha256", "signature_algorithm", "signature_b64",
}
POLICY_FIELDS = {
    "policy_version", "reviewer_id", "public_key_sha256",
    "expected_design_id", "max_attestation_age_seconds",
    "allowed_clock_skew_seconds",
}
EXPECTED_DESIGN_ID = "AURORA_G8_25_IBKR_ORDER_OBJECT_MATERIALIZER_DESIGN_V1"


def canonical_signed_payload(artifact):
    if not isinstance(artifact, dict):
        return None
    try:
        return json.dumps({k:v for k,v in artifact.items() if k!="signature_b64"},
                          sort_keys=True,separators=(",",":"),ensure_ascii=True,allow_nan=False).encode("utf-8")
    except (ValueError,TypeError,OverflowError):
        return None


def _hex(value):
    return value if isinstance(value,str) and HEX64.fullmatch(value) else None


def _date(value):
    if not isinstance(value,str) or not value:
        return None
    try:
        parsed=datetime.fromisoformat(value.replace("Z","+00:00"))
    except ValueError:
        return None
    return parsed.astimezone(timezone.utc) if parsed.tzinfo else None


def _uuid(value):
    if not isinstance(value,str):
        return None
    try:
        parsed=UUID(value)
    except (ValueError,AttributeError):
        return None
    return value if parsed.version==4 and str(parsed)==value else None


def _closed(obj):
    return isinstance(obj,dict) and all(obj.get(k) is False for k in PERMISSION_FLAGS)


def _blocked(checks):
    return {
        "engine":ENGINE_VERSION, "status":"BLOCKED", "verified":False,
        "order_object_design_independently_attested":False,
        "reason":"SIGNED_ORDER_OBJECT_DESIGN_ATTESTATION_INVALID",
        "checks":checks,
        "review_id":None, "reviewer_id":None,
        "design_sha256":None,"review_request_sha256":None,
        "upstream_attestation_result_sha256":None,"attestation_sha256":None,
        **{k:False for k in PERMISSION_FLAGS},
        "next_gate":"REPAIR_SIGNED_ORDER_OBJECT_DESIGN_ATTESTATION",
    }


def evaluate_signed_order_object_design_attestation(
    artifact, policy, public_key_bytes, signature_valid,
    handoff, design, upstream_attestation, repository_clean, *, now=None
):
    if now is None:
        now=datetime.now(timezone.utc)
    checks={}
    def check(name,passed):
        checks[name]=passed is True

    artifact=artifact if isinstance(artifact,dict) else {}
    policy=policy if isinstance(policy,dict) else {}
    handoff=handoff if isinstance(handoff,dict) else {}
    check("artifact_exact_schema",set(artifact)==ARTIFACT_FIELDS)
    check("policy_exact_schema",set(policy)==POLICY_FIELDS)
    check("decision_is_signed_review",
          artifact.get("schema_version")==1 and
          artifact.get("attestation_type")==ATTESTATION_TYPE and
          artifact.get("decision")=="ATTESTED" and
          artifact.get("signature_algorithm")=="ED25519")
    check("review_id_uuid4",_uuid(artifact.get("review_id")) is not None)
    check("signature_encoding_valid",decode_signature(artifact.get("signature_b64")) is not None)
    check("ed25519_signature_verified",signature_valid is True)

    rid=artifact.get("reviewer_id")
    check("reviewer_id_valid",isinstance(rid,str) and bool(REVIEWER.fullmatch(rid)))
    check("reviewer_matches_policy",isinstance(rid,str) and rid==policy.get("reviewer_id"))
    check("policy_identity",policy.get("policy_version")==1 and policy.get("expected_design_id")==EXPECTED_DESIGN_ID)
    key_ok=(isinstance(public_key_bytes,bytes)
            and b"-----BEGIN PUBLIC KEY-----" in public_key_bytes
            and b"PRIVATE KEY" not in public_key_bytes)
    key_hash=hashlib.sha256(public_key_bytes).hexdigest() if isinstance(public_key_bytes,bytes) else None
    check("trusted_reviewer_key_bound",key_ok and _hex(policy.get("public_key_sha256"))==key_hash)

    max_age=policy.get("max_attestation_age_seconds")
    skew=policy.get("allowed_clock_skew_seconds")
    age_ok=type(max_age) is int and 60<=max_age<=86400
    skew_ok=type(skew) is int and 0<=skew<=300
    check("time_policy_valid",age_ok and skew_ok)
    captured=_date(artifact.get("captured_at_utc"))
    expires=_date(artifact.get("expires_at_utc"))
    time_valid=(
        isinstance(now,datetime) and now.tzinfo is not None and
        captured is not None and expires is not None and age_ok and skew_ok and
        (captured-now).total_seconds()<=skew and captured<=expires and
        (expires-captured).total_seconds()<=max_age and
        (now-captured).total_seconds()<=max_age and now<=expires
        and expires>captured
    )
    check("attestation_fresh",time_valid)

    for field in (
        "reviewer_confirms_design_only","reviewer_confirms_no_broker_objects",
        "reviewer_confirms_paper_only","reviewer_confirms_transmit_false"
    ):
        check(field,artifact.get(field) is True)
    check("reviewer_evidence_digest",_hex(artifact.get("reviewer_evidence_sha256")) is not None
          and artifact.get("reviewer_evidence_sha256")!="0"*64)

    check("handoff_exact_schema",set(handoff)=={
        "engine","status","reason","ready_for_independent_review",
        "operator_attests_safe","design_sha256","upstream_attestation_result_sha256",
        "review_request_sha256","review_request","unsigned_attestation_template",
        *PERMISSION_FLAGS,"next_gate"
    })
    request=handoff.get("review_request")
    template=handoff.get("unsigned_attestation_template")
    check("handoff_not_authorizing",
          handoff.get("engine")==HANDOFF_ENGINE and
          handoff.get("status")=="READY_FOR_INDEPENDENT_ORDER_OBJECT_DESIGN_REVIEW"
          and handoff.get("ready_for_independent_review") is True
          and handoff.get("operator_attests_safe") is False
          and handoff.get("next_gate")==HANDOFF_NEXT_GATE and _closed(handoff))
    request_ok=isinstance(request,dict) and set(request)=={
        "schema_version","request_type","requested_control","generated_at_utc",
        "design_sha256","upstream_attestation_result_sha256",
        "upstream_signed_attestation_sha256","materializer_source_sha256",
        "cli_source_sha256","requires_independent_review","operator_attests_safe",
        *PERMISSION_FLAGS
    }
    check("request_exact_schema",request_ok)
    check("review_request_not_authorizing",
          request_ok and request.get("schema_version")==1 and
          request.get("request_type")==REQUEST_TYPE and
          request.get("requested_control")==ATTESTATION_TYPE and
          request.get("requires_independent_review") is True and
          request.get("operator_attests_safe") is False and _closed(request))
    check("unsigned_template_strict",
          isinstance(template,dict) and set(template)==ARTIFACT_FIELDS
          and template.get("decision")=="REVIEW_REQUIRED"
          and template.get("signature_b64") is None
          and template.get("review_id") is None
          and template.get("reviewer_id") is None
          and all(template.get(k) is None for k in (
              "reviewer_confirms_design_only","reviewer_confirms_no_broker_objects",
              "reviewer_confirms_paper_only","reviewer_confirms_transmit_false")))
    try:
        design_hash=_digest(design)
        upstream_hash=_digest(upstream_attestation)
        request_hash=_digest(request)
        rebuilt=evaluate_order_object_design_handoff(design,upstream_attestation,
                                                       now=now)
    except (TypeError,ValueError,OverflowError,AttributeError):
        design_hash=upstream_hash=request_hash=None
        rebuilt=None
    check("current_upstream_review_revalidated",
          isinstance(rebuilt,dict) and rebuilt.get("ready_for_independent_review") is True)
    check("design_hash_bound", _hex(design_hash) is not None
          and design_hash==handoff.get("design_sha256")==artifact.get("design_sha256")
          ==request.get("design_sha256") if isinstance(request,dict) else False)
    check("upstream_hash_bound",_hex(upstream_hash) is not None
          and upstream_hash==handoff.get("upstream_attestation_result_sha256")
          ==artifact.get("upstream_attestation_result_sha256")
          ==request.get("upstream_attestation_result_sha256") if isinstance(request,dict) else False)
    check("review_request_digest_bound",
          _hex(request_hash) is not None
          and request_hash==handoff.get("review_request_sha256")
          ==artifact.get("review_request_sha256"))
    check("review_rebuilt_matches_request",
          isinstance(rebuilt,dict) and isinstance(request,dict)
          and rebuilt.get("design_sha256")==handoff.get("design_sha256")
          and rebuilt.get("upstream_attestation_result_sha256")==handoff.get("upstream_attestation_result_sha256")
          and rebuilt.get("next_gate")==HANDOFF_NEXT_GATE)
    check("template_binds_hashes",
          isinstance(template,dict) and
          template.get("review_request_sha256")==handoff.get("review_request_sha256")
          and template.get("design_sha256")==handoff.get("design_sha256")
          and template.get("upstream_attestation_result_sha256")==handoff.get("upstream_attestation_result_sha256"))
    check("repository_clean",repository_clean is True)
    if not all(checks.values()):
        return _blocked(checks)
    digest=_digest(artifact)
    return {
        "engine":ENGINE_VERSION,"status":"VERIFIED","verified":True,
        "order_object_design_independently_attested":True,
        "reason":"INDEPENDENT_IBKR_ORDER_OBJECT_DESIGN_ATTESTATION_VERIFIED",
        "checks":checks,"review_id":artifact["review_id"],"reviewer_id":rid,
        "design_sha256":design_hash,"review_request_sha256":request_hash,
        "upstream_attestation_result_sha256":upstream_hash,
        "attestation_sha256":digest,
        **{k:False for k in PERMISSION_FLAGS},
        "next_gate":NEXT_GATE,
    }
