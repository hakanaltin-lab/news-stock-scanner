"""G8.30: verify independent signature for hard-disabled G8.28 candidate.

A positive result advances review state only. No broker object or order permission.
"""
from __future__ import annotations
from datetime import datetime, timezone
import hashlib
import json
import re
from uuid import UUID

from engines.ibkr_order_object_candidate_handoff import (
    ATTESTATION_TYPE, ENGINE_VERSION as HANDOFF_ENGINE,
    NEXT_GATE as HANDOFF_NEXT_GATE, REQUEST_TYPE,
    canonical_digest, evaluate_order_object_candidate_handoff,
)
from engines.ibkr_order_object_candidate_review import (
    evaluate_order_object_candidate, PERMISSION_FLAGS,
)
from engines.ibkr_order_object_design_attestation import _date, _uuid
from engines.paper_adapter_source_attestation import decode_signature

ENGINE_VERSION="AURORA G8.30 Signed Order Object Candidate Attestation"
NEXT_GATE="OFFLINE_ORDER_OBJECT_MAPPING_RESEARCH_REQUIRED"
ARTIFACT_FIELDS={
    "schema_version","attestation_type","decision","review_id","reviewer_id",
    "captured_at_utc","expires_at_utc","review_request_sha256",
    "candidate_source_sha256","candidate_review_sha256","design_sha256",
    "design_attestation_sha256","design_attestation_result_sha256",
    "reviewer_confirms_non_executable","reviewer_confirms_hard_disabled_methods",
    "reviewer_confirms_no_broker_imports","reviewer_confirms_transmit_false",
    "reviewer_evidence_sha256","signature_algorithm","signature_b64",
}
POLICY_FIELDS={
    "policy_version","reviewer_id","public_key_sha256",
    "expected_candidate_version","max_attestation_age_seconds",
    "allowed_clock_skew_seconds",
}
REVIEWER=re.compile(r"^[A-Za-z0-9._@+-]{3,128}$")
HEX64=re.compile(r"^[0-9a-f]{64}$")
EXPECTED_VERSION="AURORA_G8_28_ORDER_OBJECT_CANDIDATE_V1"
BIND_FIELDS=(
    "review_request_sha256","candidate_source_sha256",
    "candidate_review_sha256","design_sha256",
    "design_attestation_sha256","design_attestation_result_sha256",
)
CONFIRM_FIELDS=(
    "reviewer_confirms_non_executable",
    "reviewer_confirms_hard_disabled_methods",
    "reviewer_confirms_no_broker_imports",
    "reviewer_confirms_transmit_false",
)

def canonical_signed_payload(artifact):
    if not isinstance(artifact,dict):
        return None
    try:
        return json.dumps({k:v for k,v in artifact.items() if k!="signature_b64"},
                          sort_keys=True,separators=(",",":"),ensure_ascii=True,
                          allow_nan=False).encode("utf-8")
    except (ValueError,TypeError,OverflowError):
        return None

def _hex(value):
    return isinstance(value,str) and bool(HEX64.fullmatch(value))

def _closed(value):
    return isinstance(value,dict) and all(value.get(k) is False for k in PERMISSION_FLAGS)

def _blocked(checks):
    return {
        "engine":ENGINE_VERSION,"status":"BLOCKED","verified":False,
        "order_object_candidate_independently_attested":False,
        "reason":"SIGNED_ORDER_OBJECT_CANDIDATE_ATTESTATION_INVALID",
        "checks":checks,"review_id":None,"reviewer_id":None,
        "candidate_source_sha256":None,"review_request_sha256":None,
        "candidate_review_sha256":None,"design_sha256":None,
        "design_attestation_sha256":None,"attestation_sha256":None,
        **{k:False for k in PERMISSION_FLAGS},
        "next_gate":"REPAIR_SIGNED_ORDER_OBJECT_CANDIDATE_ATTESTATION",
    }

def evaluate_signed_order_object_candidate_attestation(
    artifact,policy,public_key_bytes,signature_valid,
    handoff,candidate_source,candidate_review,design_attestation,
    repository_clean,*,now=None,
):
    if now is None:now=datetime.now(timezone.utc)
    checks={}
    def check(name,value):checks[name]=value is True
    artifact=artifact if isinstance(artifact,dict) else {}
    policy=policy if isinstance(policy,dict) else {}
    handoff=handoff if isinstance(handoff,dict) else {}
    check("artifact_schema",set(artifact)==ARTIFACT_FIELDS)
    check("policy_schema",set(policy)==POLICY_FIELDS)
    check("attested_decision",
          type(artifact.get("schema_version")) is int and artifact.get("schema_version")==1
          and artifact.get("attestation_type")==ATTESTATION_TYPE
          and artifact.get("decision")=="ATTESTED"
          and artifact.get("signature_algorithm")=="ED25519")
    check("review_id_uuid4",_uuid(artifact.get("review_id")) is not None)
    rid=artifact.get("reviewer_id")
    check("reviewer_identity",isinstance(rid,str)
          and bool(REVIEWER.fullmatch(rid)) and rid==policy.get("reviewer_id"))
    check("signature_encoding",decode_signature(artifact.get("signature_b64")) is not None)
    check("ed25519_signature_verified",signature_valid is True)
    check("policy_identity",
          type(policy.get("policy_version")) is int and policy.get("policy_version")==1
          and policy.get("expected_candidate_version")==EXPECTED_VERSION)
    valid_key=(isinstance(public_key_bytes,bytes)
               and public_key_bytes.startswith(b"-----BEGIN PUBLIC KEY-----")
               and b"PRIVATE KEY" not in public_key_bytes)
    key_hash=hashlib.sha256(public_key_bytes).hexdigest() if isinstance(public_key_bytes,bytes) else None
    check("reviewer_public_key_bound",
          valid_key and _hex(policy.get("public_key_sha256"))
          and policy.get("public_key_sha256")==key_hash)
    max_age=policy.get("max_attestation_age_seconds")
    skew=policy.get("allowed_clock_skew_seconds")
    valid_policy=(type(max_age) is int and 60<=max_age<=86400
                  and type(skew) is int and 0<=skew<=300)
    check("time_policy",valid_policy)
    capture=_date(artifact.get("captured_at_utc"))
    expiry=_date(artifact.get("expires_at_utc"))
    # Require timezone-aware timestamps within the configured review window.
    valid_clock=(isinstance(now,datetime) and now.tzinfo is not None)
    fresh=(valid_clock and capture is not None and expiry is not None and valid_policy
           and capture<expiry
           and (capture-now).total_seconds()<=skew
           and (now-capture).total_seconds()<=max_age
           and (expiry-capture).total_seconds()<=max_age
           and now<=expiry)
    check("review_fresh",fresh)
    for flag in CONFIRM_FIELDS:
        check(flag,artifact.get(flag) is True)
    evidence=artifact.get("reviewer_evidence_sha256")
    check("reviewer_evidence",_hex(evidence) and evidence!="0"*64)
    check("repository_clean",repository_clean is True)
    check("handoff_state",
          handoff.get("engine")==HANDOFF_ENGINE
          and handoff.get("status")=="READY_FOR_INDEPENDENT_ORDER_OBJECT_CANDIDATE_REVIEW"
          and handoff.get("ready_for_independent_review") is True
          and handoff.get("candidate_revalidated") is True
          and handoff.get("operator_attests_candidate_safe") is False
          and handoff.get("next_gate")==HANDOFF_NEXT_GATE
          and _closed(handoff))
    request=handoff.get("review_request")
    template=handoff.get("unsigned_attestation_template")
    check("request_not_authorizing",
          isinstance(request,dict)
          and request.get("schema_version")==1
          and request.get("request_type")==REQUEST_TYPE
          and request.get("requested_control")==ATTESTATION_TYPE
          and request.get("requires_independent_human_review") is True
          and request.get("operator_attests_candidate_safe") is False
          and request.get("candidate_imported") is False
          and request.get("broker_object_created") is False
          and request.get("network_accessed") is False
          and _closed(request))
    check("template_unsigned",
          isinstance(template,dict)
          and set(template)==ARTIFACT_FIELDS
          and template.get("decision")=="REVIEW_REQUIRED"
          and template.get("signature_b64") is None
          and template.get("review_id") is None
          and template.get("reviewer_id") is None
          and all(template.get(k) is None for k in CONFIRM_FIELDS))
    try:
        candidate_again=evaluate_order_object_candidate(design_attestation,candidate_source,now=now)
        handoff_again=evaluate_order_object_candidate_handoff(
            candidate_review,candidate_source,design_attestation,now=now)
        request_digest=canonical_digest(request)
        review_digest=canonical_digest(candidate_review)
        attestation_digest=canonical_digest(design_attestation)
        source_digest=hashlib.sha256(candidate_source.encode("utf-8")).hexdigest()
    except (TypeError,ValueError,OverflowError,AttributeError,UnicodeError):
        candidate_again=handoff_again=None
        request_digest=review_digest=attestation_digest=source_digest=None
    check("candidate_reverified",candidate_again==candidate_review
          and isinstance(candidate_again,dict)
          and candidate_again.get("candidate_validated") is True)
    check("handoff_reverified",
          isinstance(handoff_again,dict)
          and handoff_again.get("ready_for_independent_review") is True
          and handoff_again.get("candidate_review_sha256")==handoff.get("candidate_review_sha256")
          and handoff_again.get("review_request",{}).get("candidate_source_sha256")
          ==request.get("candidate_source_sha256") if isinstance(request,dict) else False)
    expected={
        "review_request_sha256":request_digest,
        "candidate_source_sha256":source_digest,
        "candidate_review_sha256":review_digest,
        "design_sha256":candidate_review.get("design_sha256") if isinstance(candidate_review,dict) else None,
        "design_attestation_sha256":candidate_review.get("design_attestation_sha256") if isinstance(candidate_review,dict) else None,
        "design_attestation_result_sha256":attestation_digest,
    }
    check("artifact_request_bindings",
          isinstance(request,dict) and all(
              _hex(digest) and artifact.get(field)==digest
              and (field=="review_request_sha256" or request.get(field)==digest)
              for field,digest in expected.items()
          ))
    check("handoff_request_digest",
          _hex(request_digest) and request_digest==handoff.get("review_request_sha256"))
    check("handoff_review_digest",
          _hex(review_digest) and review_digest==handoff.get("candidate_review_sha256"))
    check("template_exact_bindings",
          isinstance(template,dict)
          and all(template.get(field)==digest for field,digest in expected.items()))
    if not all(checks.values()):
        return _blocked(checks)
    return {
        "engine":ENGINE_VERSION,"status":"VERIFIED","verified":True,
        "order_object_candidate_independently_attested":True,
        "reason":"INDEPENDENT_ORDER_OBJECT_CANDIDATE_ATTESTATION_VERIFIED",
        "checks":checks,"review_id":artifact["review_id"],"reviewer_id":rid,
        "candidate_source_sha256":source_digest,
        "review_request_sha256":request_digest,
        "candidate_review_sha256":review_digest,
        "design_sha256":expected["design_sha256"],
        "design_attestation_sha256":expected["design_attestation_sha256"],
        "attestation_sha256":canonical_digest(artifact),
        **{k:False for k in PERMISSION_FLAGS},
        "next_gate":NEXT_GATE,
    }
