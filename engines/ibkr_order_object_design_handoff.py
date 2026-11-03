"""G8.26 unsigned independent-review handoff for the G8.25 design.

This module does not sign, approve, import ibapi, create broker objects,
connect to a broker or authorize execution.
"""
from __future__ import annotations
from datetime import datetime, timezone
import hashlib
import json
from engines.ibkr_order_object_materializer_design import (
    DESIGN_NEXT_GATE, ENGINE_VERSION as DESIGN_ENGINE,
    evaluate_ibkr_order_object_design,
)
from engines.paper_adapter_implementation_candidate_review import PERMISSION_FLAGS

ENGINE_VERSION = "AURORA G8.26 IBKR Order Object Design Review Handoff"
REQUEST_TYPE = "AURORA_IBKR_ORDER_OBJECT_DESIGN_REVIEW_REQUEST_V1"
ATTESTATION_TYPE = "AURORA_IBKR_ORDER_OBJECT_DESIGN_ATTESTATION_V1"
NEXT_GATE = "SIGNED_INDEPENDENT_IBKR_ORDER_OBJECT_DESIGN_ATTESTATION_REQUIRED"

def _digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=True,allow_nan=False).encode("utf-8")).hexdigest()

def _permissions_closed(value):
    return isinstance(value,dict) and all(value.get(k) is False for k in PERMISSION_FLAGS)

def _blocked(reason):
    return {
        "engine":ENGINE_VERSION,"status":"BLOCKED","reason":reason,
        "ready_for_independent_review":False,"operator_attests_safe":False,
        "review_request":None,"unsigned_attestation_template":None,
        **{k:False for k in PERMISSION_FLAGS},
        "next_gate":"REPAIR_ORDER_OBJECT_DESIGN_REVIEW_HANDOFF",
    }

def evaluate_order_object_design_handoff(design, materializer_attestation, *, now=None):
    if now is None:
        now=datetime.now(timezone.utc)
    if not isinstance(now,datetime) or now.tzinfo is None:
        return _blocked("INVALID_CLOCK")
    if not isinstance(design,dict) or not isinstance(materializer_attestation,dict):
        return _blocked("INVALID_INPUT")
    try:
        evaluated=evaluate_ibkr_order_object_design(design,materializer_attestation,now=now)
    except (ValueError,TypeError,OverflowError):
        return _blocked("UPSTREAM_EVALUATION_FAILED")
    if not (
        evaluated.get("engine")==DESIGN_ENGINE
        and evaluated.get("status")=="DESIGN_VALIDATED_NON_EXECUTABLE"
        and evaluated.get("design_validated") is True
        and evaluated.get("materializer_attestation_verified") is True
        and evaluated.get("next_gate")==DESIGN_NEXT_GATE
        and _permissions_closed(evaluated)
    ):
        return _blocked("DESIGN_OR_UPSTREAM_ATTESTATION_NOT_VALID")
    try:
        design_digest=_digest(design)
        upstream_digest=_digest(materializer_attestation)
    except (TypeError,ValueError,OverflowError):
        return _blocked("INPUT_DIGEST_INVALID")
    if design_digest!=evaluated.get("design_sha256"):
        return _blocked("DESIGN_DIGEST_MISMATCH")
    request={
        "schema_version":1,"request_type":REQUEST_TYPE,
        "requested_control":ATTESTATION_TYPE,
        "generated_at_utc":now.astimezone(timezone.utc).isoformat(),
        "design_sha256":design_digest,
        "upstream_attestation_result_sha256":upstream_digest,
        "upstream_signed_attestation_sha256":evaluated["materializer_attestation_sha256"],
        "materializer_source_sha256":evaluated["materializer_source_sha256"],
        "cli_source_sha256":evaluated["cli_source_sha256"],
        "requires_independent_review":True,
        "operator_attests_safe":False,
        **{k:False for k in PERMISSION_FLAGS},
    }
    request_digest=_digest(request)
    unsigned={
        "schema_version":1,"attestation_type":ATTESTATION_TYPE,
        "decision":"REVIEW_REQUIRED",
        "review_id":None,"reviewer_id":None,
        "captured_at_utc":None,"expires_at_utc":None,
        "review_request_sha256":request_digest,
        "design_sha256":design_digest,
        "upstream_attestation_result_sha256":upstream_digest,
        "reviewer_confirms_design_only":None,
        "reviewer_confirms_no_broker_objects":None,
        "reviewer_confirms_paper_only":None,
        "reviewer_confirms_transmit_false":None,
        "reviewer_evidence_sha256":None,
        "signature_algorithm":"ED25519","signature_b64":None,
    }
    return {
        "engine":ENGINE_VERSION,
        "status":"READY_FOR_INDEPENDENT_ORDER_OBJECT_DESIGN_REVIEW",
        "reason":"SIGNED_INDEPENDENT_REVIEW_REQUIRED",
        "ready_for_independent_review":True,
        "operator_attests_safe":False,
        "design_sha256":design_digest,
        "upstream_attestation_result_sha256":upstream_digest,
        "review_request_sha256":request_digest,
        "review_request":request,
        "unsigned_attestation_template":unsigned,
        **{k:False for k in PERMISSION_FLAGS},
        "next_gate":NEXT_GATE,
    }
