"""G8.32 unsigned independent review handoff for offline IBKR field mappings.

No candidate import, signing key, broker objects, networking or orders.
"""
from __future__ import annotations
from datetime import datetime, timezone
from engines.ibkr_offline_order_object_mapping import (
    ENGINE_VERSION as MAPPING_ENGINE, NEXT_GATE as MAPPING_NEXT_GATE,
    _digest, _sha, research_offline_ibkr_mapping,
)
from engines.paper_adapter_implementation_candidate_review import PERMISSION_FLAGS

ENGINE_VERSION="AURORA G8.32 Offline IBKR Mapping Review Handoff"
REQUEST_TYPE="AURORA_IBKR_OFFLINE_MAPPING_REVIEW_REQUEST_V1"
ATTESTATION_TYPE="AURORA_IBKR_OFFLINE_MAPPING_REVIEW_ATTESTATION_V1"
NEXT_GATE="SIGNED_INDEPENDENT_OFFLINE_MAPPING_REVIEW_REQUIRED"
MAPPING_RESULT_FIELDS={
    "engine","status","reason","mapping_preview_validated","mapping",
    "mapping_sha256","candidate_attestation_verified",
    "broker_order_object_created","network_accessed","transmit",
    *PERMISSION_FLAGS,"next_gate",
}
def _closed(value):
    return isinstance(value,dict) and all(value.get(k) is False for k in PERMISSION_FLAGS)

def _blocked(reason):
    return {
        "engine":ENGINE_VERSION,"status":"BLOCKED","reason":reason,
        "ready_for_independent_review":False,"mapping_revalidated":False,
        "operator_approves_execution":False,
        "review_request_sha256":None,"review_request":None,
        "unsigned_attestation_template":None,
        **{k:False for k in PERMISSION_FLAGS},
        "next_gate":"REPAIR_G8_32_OFFLINE_MAPPING_HANDOFF",
    }

def create_offline_mapping_review_handoff(design,attestation,preview,mapping_result,*,now=None):
    if now is None:now=datetime.now(timezone.utc)
    if not isinstance(now,datetime) or now.tzinfo is None:
        return _blocked("CLOCK_INVALID")
    if not isinstance(mapping_result,dict) or set(mapping_result)!=MAPPING_RESULT_FIELDS:
        return _blocked("MAPPING_RESULT_SCHEMA_INVALID")
    if not isinstance(preview,dict) or not isinstance(attestation,dict):
        return _blocked("REVIEW_INPUT_INVALID")
    if not (
        mapping_result.get("engine")==MAPPING_ENGINE
        and mapping_result.get("status")=="OFFLINE_IBKR_MAPPING_RESEARCH_VALIDATED"
        and mapping_result.get("reason")=="INDEPENDENT_OFFLINE_MAPPING_REVIEW_REQUIRED"
        and mapping_result.get("mapping_preview_validated") is True
        and mapping_result.get("candidate_attestation_verified") is True
        and mapping_result.get("next_gate")==MAPPING_NEXT_GATE
        and mapping_result.get("broker_order_object_created") is False
        and mapping_result.get("network_accessed") is False
        and mapping_result.get("transmit") is False
        and _closed(mapping_result)
    ):
        return _blocked("MAPPING_RESULT_UNSAFE")
    # G8.31 accepts a syntactically valid preview attestation digest. G8.32
    # additionally binds it to the exact independently attested G8.30 evidence.
    if not (
        _sha(preview.get("candidate_attestation_sha256"))
        and preview.get("candidate_attestation_sha256")==attestation.get("attestation_sha256")
    ):
        return _blocked("PREVIEW_ATTESTATION_BINDING_MISMATCH")
    rebuilt=research_offline_ibkr_mapping(design,attestation,preview)
    if rebuilt!=mapping_result:
        return _blocked("MAPPING_NOT_REPRODUCIBLE")
    mapping=mapping_result.get("mapping")
    if not isinstance(mapping,dict):
        return _blocked("MAPPING_INVALID")
    if not (
        mapping.get("research_only") is True
        and mapping.get("paper_only") is True
        and all(mapping.get(k) is False for k in (
            "ibkr_contract_instantiated","ibkr_order_instantiated",
            "order_id_allocated","connection_established",
            "network_accessed","broker_order_submitted"))
        and mapping.get("order_fields",{}).get("transmit") is False
        and mapping.get("candidate_attestation_sha256")==attestation["attestation_sha256"]
        and mapping.get("order_preview_sha256")==_digest(preview)
        and mapping.get("design_sha256")==_digest(design)
        and mapping_result.get("mapping_sha256")==_digest(mapping)
    ):
        return _blocked("MAPPING_SAFETY_FLAGS_INVALID")
    design_sha=_digest(design)
    upstream_sha=_digest(attestation)
    preview_sha=_digest(preview)
    mapping_result_sha=_digest(mapping_result)
    if not all(_sha(v) for v in (
        design_sha,upstream_sha,preview_sha,mapping_result_sha
    )):
        return _blocked("REVIEW_DIGEST_INVALID")
    request={
        "schema_version":1,
        "request_type":REQUEST_TYPE,
        "requested_control":ATTESTATION_TYPE,
        "generated_at_utc":now.astimezone(timezone.utc).isoformat(),
        "design_sha256":design_sha,
        "signed_candidate_attestation_sha256":attestation["attestation_sha256"],
        "candidate_attestation_result_sha256":upstream_sha,
        "normalized_preview_sha256":preview_sha,
        "mapping_result_sha256":mapping_result_sha,
        "mapping_sha256":mapping_result["mapping_sha256"],
        "independent_human_review_required":True,
        "operator_approves_execution":False,
        "broker_contract_created":False,
        "broker_order_created":False,
        "network_accessed":False,
        "transmit":False,
        **{k:False for k in PERMISSION_FLAGS},
    }
    request_sha=_digest(request)
    template={
        "schema_version":1,"attestation_type":ATTESTATION_TYPE,
        "decision":"REVIEW_REQUIRED",
        "review_id":None,"reviewer_id":None,
        "captured_at_utc":None,"expires_at_utc":None,
        "review_request_sha256":request_sha,
        "design_sha256":design_sha,
        "signed_candidate_attestation_sha256":attestation["attestation_sha256"],
        "candidate_attestation_result_sha256":upstream_sha,
        "normalized_preview_sha256":preview_sha,
        "mapping_result_sha256":mapping_result_sha,
        "mapping_sha256":mapping_result["mapping_sha256"],
        "reviewer_confirms_paper_only":None,
        "reviewer_confirms_no_broker_objects":None,
        "reviewer_confirms_no_network_or_submission":None,
        "reviewer_confirms_transmit_false":None,
        "reviewer_confirms_preview_attestation_bound":None,
        "reviewer_evidence_sha256":None,
        "signature_algorithm":"ED25519","signature_b64":None,
    }
    return {
        "engine":ENGINE_VERSION,
        "status":"READY_FOR_INDEPENDENT_OFFLINE_MAPPING_REVIEW",
        "reason":"SIGNED_INDEPENDENT_MAPPING_REVIEW_REQUIRED",
        "ready_for_independent_review":True,
        "mapping_revalidated":True,
        "operator_approves_execution":False,
        "review_request_sha256":request_sha,
        "review_request":request,
        "unsigned_attestation_template":template,
        **{k:False for k in PERMISSION_FLAGS},
        "next_gate":NEXT_GATE,
    }
