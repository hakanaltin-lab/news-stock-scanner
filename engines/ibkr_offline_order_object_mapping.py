"""G8.31 research-only IBKR field mapping; never constructs broker objects.

Produces plain dictionaries strictly for offline inspection. An independently
verified G8.30 candidate attestation is necessary but never grants execution.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
import hashlib
import json
import re

from engines.ibkr_order_object_candidate_attestation import (
    ENGINE_VERSION as REVIEW_ENGINE, NEXT_GATE as REVIEW_NEXT_GATE,
)
from engines.paper_adapter_implementation_candidate_review import PERMISSION_FLAGS
from engines.ibkr_order_object_materializer_design import (
    DESIGN_ID, DESIGN_FIELDS, EXPECTED_CONTRACT_MAPPING,
    EXPECTED_ORDER_MAPPING,
)

ENGINE_VERSION = "AURORA G8.31 Offline IBKR Field Mapping Research"
NEXT_GATE = "INDEPENDENT_OFFLINE_IBKR_MAPPING_REVIEW_REQUIRED"
HEX64 = re.compile(r"^[0-9a-f]{64}$")
SYMBOL = re.compile(r"^[A-Z][A-Z0-9.-]{0,11}$")
PRICE = re.compile(r"^[0-9]{1,8}(?:\\.[0-9]{1,4})?$")
ATTESTATION_FIELDS = {
    "engine","status","verified","order_object_candidate_independently_attested",
    "reason","checks","review_id","reviewer_id","candidate_source_sha256",
    "review_request_sha256","candidate_review_sha256","design_sha256",
    "design_attestation_sha256","attestation_sha256",*PERMISSION_FLAGS,"next_gate",
}
REQUEST_FIELDS = {
    "request_schema_version","intent_id","symbol","side","quantity",
    "position_quantity_at_validation","limit_price","order_type",
    "time_in_force","outside_rth","reduce_only","paper_only","transmit",
    "broker_request_materialized","broker_order_object_created",
    "candidate_attestation_sha256",
}
def _blocked(reason):
    return {
        "engine":ENGINE_VERSION,"status":"BLOCKED","reason":reason,
        "mapping_preview_validated":False,"mapping":None,
        "mapping_sha256":None,"candidate_attestation_verified":False,
        "broker_order_object_created":False,"network_accessed":False,
        "transmit":False,
        **{f:False for f in PERMISSION_FLAGS},
        "next_gate":"REPAIR_G8_31_OFFLINE_MAPPING_RESEARCH",
    }

def _sha(value):
    return isinstance(value,str) and HEX64.fullmatch(value) is not None

def _digest(value):
    try:
        return hashlib.sha256(json.dumps(value,sort_keys=True,
            separators=(",",":"),ensure_ascii=True,allow_nan=False).encode()).hexdigest()
    except (TypeError,ValueError,OverflowError):
        return None

def _attested(attestation):
    return (
        isinstance(attestation,dict) and set(attestation)==ATTESTATION_FIELDS
        and attestation.get("engine")==REVIEW_ENGINE
        and attestation.get("status")=="VERIFIED"
        and attestation.get("verified") is True
        and attestation.get("order_object_candidate_independently_attested") is True
        and attestation.get("reason")=="INDEPENDENT_ORDER_OBJECT_CANDIDATE_ATTESTATION_VERIFIED"
        and attestation.get("next_gate")==REVIEW_NEXT_GATE
        and isinstance(attestation.get("checks"),dict)
        and bool(attestation["checks"])
        and all(v is True for v in attestation["checks"].values())
        and all(attestation.get(f) is False for f in PERMISSION_FLAGS)
        and all(_sha(attestation.get(f)) for f in (
            "candidate_source_sha256","review_request_sha256",
            "candidate_review_sha256","design_sha256",
            "design_attestation_sha256","attestation_sha256"))
    )

def _design_safe(design):
    return (
        isinstance(design,dict) and set(design)==DESIGN_FIELDS
        and type(design.get("schema_version")) is int and design["schema_version"]==1
        and design.get("design_id")==DESIGN_ID
        and design.get("design_status")=="REVIEW_REQUIRED"
        and design.get("target_api")=="IBKR_TWS_API"
        and design.get("broker_mode")=="PAPER"
        and design.get("host")=="127.0.0.1"
        and type(design.get("port")) is int and design["port"]==4002
        and design.get("asset_type")=="STK"
        and design.get("accepted_request_schema_version")==1
        and design.get("accepted_order_type")=="LMT"
        and design.get("accepted_time_in_force")=="DAY"
        and design.get("contract_class")=="ibapi.contract.Contract"
        and design.get("order_class")=="ibapi.order.Order"
        and design.get("planned_contract_mapping")==EXPECTED_CONTRACT_MAPPING
        and design.get("planned_order_mapping")==EXPECTED_ORDER_MAPPING
        and all(design.get(f) is False for f in PERMISSION_FLAGS)
        and all(design.get(f) is False for f in (
            "ibkr_import_allowed","network_allowed","order_id_allocation_allowed",
            "contract_resolution_allowed","outside_rth_allowed","market_order_allowed",
            "short_selling_allowed","fractional_quantity_allowed",
            "raw_account_id_allowed","credentials_allowed"))
        and design.get("transmit_must_be_false") is True
        and design.get("materializer_attestation_required") is True
        and design.get("requires_independent_design_review") is True
        and design.get("signed_design_attestation_required") is True
    )

def research_offline_ibkr_mapping(design,attestation,request):
    if not _attested(attestation):
        return _blocked("INDEPENDENT_CANDIDATE_ATTESTATION_NOT_VERIFIED")
    if not _design_safe(design):
        return _blocked("IBKR_DESIGN_NOT_SAFE")
    if _digest(design)!=attestation.get("design_sha256"):
        return _blocked("SIGNED_DESIGN_DIGEST_MISMATCH")
    if not isinstance(request,dict) or set(request)!=REQUEST_FIELDS:
        return _blocked("REQUEST_SCHEMA_INVALID")
    qty=request.get("quantity")
    position=request.get("position_quantity_at_validation")
    sym=request.get("symbol")
    side=request.get("side")
    price=request.get("limit_price")
    if not (
        type(request.get("request_schema_version")) is int
        and request.get("request_schema_version")==1
        and isinstance(request.get("intent_id"),str)
        and re.fullmatch(r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}",request["intent_id"])
        and isinstance(sym,str) and SYMBOL.fullmatch(sym)
        and side in ("BUY","SELL")
        and type(qty) is int and 1<=qty<=100000
        and type(position) is int and position>=0
        and isinstance(price,str) and PRICE.fullmatch(price)
        and request.get("order_type")=="LMT"
        and request.get("time_in_force")=="DAY"
        and request.get("outside_rth") is False
        and request.get("paper_only") is True
        and request.get("transmit") is False
        and request.get("broker_request_materialized") is False
        and request.get("broker_order_object_created") is False
        and _sha(request.get("candidate_attestation_sha256"))
        and type(request.get("reduce_only")) is bool
    ):
        return _blocked("ORDER_PREVIEW_NOT_SAFE")
    if (side=="SELL" and (request["reduce_only"] is not True or qty>position)) or (
        side=="BUY" and request["reduce_only"] is not False
    ):
        return _blocked("SELL_COVERAGE_OR_REDUCE_ONLY_INVALID")
    try:
        decimal=Decimal(price)
    except (InvalidOperation,ValueError):
        return _blocked("INVALID_LIMIT_PRICE")
    if not decimal.is_finite() or decimal<=0 or format(decimal.normalize(),"f")!=price:
        return _blocked("NONCANONICAL_LIMIT_PRICE")
    mapping={
        "contract_fields":{"symbol":sym,"secType":"STK","exchange":"SMART","currency":"USD"},
        "order_fields":{
            "action":side,"totalQuantity":qty,"orderType":"LMT",
            "lmtPrice":price,"tif":"DAY","outsideRth":False,"transmit":False,
        },
        "research_only":True,
        "paper_only":True,
        "candidate_attestation_sha256":attestation["attestation_sha256"],
        "order_preview_sha256":_digest(request),
        "design_sha256":attestation["design_sha256"],
        "ibkr_contract_instantiated":False,
        "ibkr_order_instantiated":False,
        "order_id_allocated":False,
        "connection_established":False,
        "network_accessed":False,
        "broker_order_submitted":False,
    }
    return {
        "engine":ENGINE_VERSION,
        "status":"OFFLINE_IBKR_MAPPING_RESEARCH_VALIDATED",
        "reason":"INDEPENDENT_OFFLINE_MAPPING_REVIEW_REQUIRED",
        "mapping_preview_validated":True,
        "mapping":mapping,
        "mapping_sha256":_digest(mapping),
        "candidate_attestation_verified":True,
        "broker_order_object_created":False,"network_accessed":False,"transmit":False,
        **{f:False for f in PERMISSION_FLAGS},
        "next_gate":NEXT_GATE,
    }
