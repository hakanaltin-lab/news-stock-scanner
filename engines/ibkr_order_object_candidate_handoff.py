"""G8.29 non-attesting handoff for G8.28 order-object candidate.

No candidate import, private signing key, broker API, or execution permission.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import re

from engines.ibkr_order_object_candidate_review import (
    ENGINE_VERSION as CANDIDATE_ENGINE,
    NEXT_GATE as CANDIDATE_NEXT_GATE,
    evaluate_order_object_candidate,
)
from engines.ibkr_order_object_design_attestation import (
    ENGINE_VERSION as DESIGN_ATTESTATION_ENGINE,
    NEXT_GATE as DESIGN_ATTESTATION_NEXT_GATE,
)
from engines.paper_adapter_implementation_candidate_review import PERMISSION_FLAGS

ENGINE_VERSION = "AURORA G8.29 Order Object Candidate Review Handoff"
REQUEST_TYPE = "AURORA_IBKR_ORDER_OBJECT_CANDIDATE_REVIEW_REQUEST_V1"
ATTESTATION_TYPE = "AURORA_IBKR_ORDER_OBJECT_CANDIDATE_ATTESTATION_V1"
NEXT_GATE = "SIGNED_INDEPENDENT_ORDER_OBJECT_CANDIDATE_ATTESTATION_REQUIRED"
HEX64 = re.compile(r"^[0-9a-f]{64}$")
CANDIDATE_REVIEW_FIELDS = {
    "engine","status","reason","candidate_validated",
    "design_attestation_verified","candidate_source_sha256",
    "design_sha256","design_attestation_sha256",
    *PERMISSION_FLAGS,"next_gate",
}
DESIGN_ATTESTATION_FIELDS = {
    "engine","status","verified",
    "order_object_design_independently_attested","reason","checks",
    "review_id","reviewer_id","design_sha256","review_request_sha256",
    "upstream_attestation_result_sha256","attestation_sha256",
    *PERMISSION_FLAGS,"next_gate",
}
def canonical_digest(value):
    if not isinstance(value,dict):
        return None
    try:
        raw=json.dumps(value,sort_keys=True,separators=(",",":"),
                       ensure_ascii=True,allow_nan=False).encode("utf-8")
    except (TypeError,ValueError,OverflowError):
        return None
    return hashlib.sha256(raw).hexdigest()

def _hex64(value):
    return isinstance(value,str) and bool(HEX64.fullmatch(value))

def _closed(value):
    return isinstance(value,dict) and all(value.get(k) is False for k in PERMISSION_FLAGS)

def _blocked(reason):
    return {
        "engine":ENGINE_VERSION,"status":"BLOCKED","reason":reason,
        "ready_for_independent_review":False,
        "candidate_revalidated":False,
        "operator_attests_candidate_safe":False,
        "candidate_review_sha256":None,"review_request_sha256":None,
        "review_request":None,"unsigned_attestation_template":None,
        **{k:False for k in PERMISSION_FLAGS},
        "next_gate":"REPAIR_ORDER_OBJECT_CANDIDATE_REVIEW_HANDOFF",
    }

def evaluate_order_object_candidate_handoff(candidate_review,candidate_source,
                                            design_attestation,*,now=None):
    if now is None:
        now=datetime.now(timezone.utc)
    if not isinstance(now,datetime) or now.tzinfo is None:
        return _blocked("CLOCK_INVALID")
    if not isinstance(candidate_source,str) or not candidate_source:
        return _blocked("CANDIDATE_SOURCE_INVALID")
    if not isinstance(candidate_review,dict) or set(candidate_review)!=CANDIDATE_REVIEW_FIELDS:
        return _blocked("CANDIDATE_REVIEW_SCHEMA_INVALID")
    if not isinstance(design_attestation,dict) or set(design_attestation)!=DESIGN_ATTESTATION_FIELDS:
        return _blocked("DESIGN_ATTESTATION_SCHEMA_INVALID")
    if not (
        candidate_review.get("engine")==CANDIDATE_ENGINE
        and candidate_review.get("status")=="NON_EXECUTABLE_ORDER_OBJECT_CANDIDATE_VALIDATED"
        and candidate_review.get("reason")=="INDEPENDENT_CANDIDATE_REVIEW_REQUIRED"
        and candidate_review.get("candidate_validated") is True
        and candidate_review.get("design_attestation_verified") is True
        and candidate_review.get("next_gate")==CANDIDATE_NEXT_GATE
        and _closed(candidate_review)
    ):
        return _blocked("CANDIDATE_REVIEW_NOT_SAFE")
    if not (
        design_attestation.get("engine")==DESIGN_ATTESTATION_ENGINE
        and design_attestation.get("status")=="VERIFIED"
        and design_attestation.get("verified") is True
        and design_attestation.get("order_object_design_independently_attested") is True
        and design_attestation.get("next_gate")==DESIGN_ATTESTATION_NEXT_GATE
        and _closed(design_attestation)
    ):
        return _blocked("DESIGN_ATTESTATION_NOT_VERIFIED")
    try:
        reevaluated=evaluate_order_object_candidate(design_attestation,candidate_source,now=now)
    except (ValueError,TypeError,OverflowError):
        return _blocked("CANDIDATE_REVALIDATION_EXCEPTION")
    if reevaluated!=candidate_review:
        return _blocked("CANDIDATE_REVALIDATION_MISMATCH")
    source_digest=hashlib.sha256(candidate_source.encode("utf-8")).hexdigest()
    attestation_digest=canonical_digest(design_attestation)
    review_digest=canonical_digest(candidate_review)
    if not (
        source_digest==candidate_review.get("candidate_source_sha256")
        and candidate_review.get("design_sha256")==design_attestation.get("design_sha256")
        and candidate_review.get("design_attestation_sha256")==design_attestation.get("attestation_sha256")
        and _hex64(source_digest) and _hex64(attestation_digest) and _hex64(review_digest)
    ):
        return _blocked("SOURCE_OR_REVIEW_BINDING_INVALID")
    request={
        "schema_version":1,
        "request_type":REQUEST_TYPE,
        "requested_control":ATTESTATION_TYPE,
        "generated_at_utc":now.astimezone(timezone.utc).isoformat(),
        "candidate_source_sha256":source_digest,
        "candidate_review_sha256":review_digest,
        "design_sha256":candidate_review["design_sha256"],
        "design_attestation_sha256":candidate_review["design_attestation_sha256"],
        "design_attestation_result_sha256":attestation_digest,
        "requires_independent_human_review":True,
        "operator_attests_candidate_safe":False,
        "candidate_imported":False,
        "broker_object_created":False,
        "network_accessed":False,
        **{k:False for k in PERMISSION_FLAGS},
    }
    request_digest=canonical_digest(request)
    template={
        "schema_version":1,
        "attestation_type":ATTESTATION_TYPE,
        "decision":"REVIEW_REQUIRED",
        "review_id":None,"reviewer_id":None,
        "captured_at_utc":None,"expires_at_utc":None,
        "review_request_sha256":request_digest,
        "candidate_source_sha256":source_digest,
        "candidate_review_sha256":review_digest,
        "design_sha256":candidate_review["design_sha256"],
        "design_attestation_sha256":candidate_review["design_attestation_sha256"],
        "design_attestation_result_sha256":attestation_digest,
        "reviewer_confirms_non_executable":None,
        "reviewer_confirms_hard_disabled_methods":None,
        "reviewer_confirms_no_broker_imports":None,
        "reviewer_confirms_transmit_false":None,
        "reviewer_evidence_sha256":None,
        "signature_algorithm":"ED25519","signature_b64":None,
    }
    return {
        "engine":ENGINE_VERSION,
        "status":"READY_FOR_INDEPENDENT_ORDER_OBJECT_CANDIDATE_REVIEW",
        "reason":"SIGNED_HUMAN_CANDIDATE_REVIEW_REQUIRED",
        "ready_for_independent_review":True,
        "candidate_revalidated":True,
        "operator_attests_candidate_safe":False,
        "candidate_review_sha256":review_digest,
        "review_request_sha256":request_digest,
        "review_request":request,
        "unsigned_attestation_template":template,
        **{k:False for k in PERMISSION_FLAGS},
        "next_gate":NEXT_GATE,
    }
