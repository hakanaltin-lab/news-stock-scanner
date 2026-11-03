"""G8.28 AST-only review: candidate must be byte-for-byte shaped as frozen skeleton."""
from __future__ import annotations

import ast
from datetime import datetime, timezone
import hashlib
import json
import re
from engines.ibkr_order_object_design_attestation import ENGINE_VERSION as REVIEW_ENGINE, NEXT_GATE as REVIEW_NEXT_GATE
from engines.paper_adapter_implementation_candidate_review import PERMISSION_FLAGS

ENGINE_VERSION = "AURORA G8.28 Non-executable Order Object Candidate"
NEXT_GATE = "INDEPENDENT_ORDER_OBJECT_CANDIDATE_REVIEW_REQUIRED"
VERSION = "AURORA_G8_28_ORDER_OBJECT_CANDIDATE_V1"
DESIGN_ID = "AURORA_G8_25_IBKR_ORDER_OBJECT_MATERIALIZER_DESIGN_V1"
CLASS_NAME = "IBKROrderObjectMaterializerCandidate"
REQUIRED_METHODS = {
    "__init__", "describe", "connect", "create_contract",
    "create_order", "submit_order", "cancel_order", "modify_order",
}
BLOCK_REASONS = {
    "connect": "G8_28_CONNECTION_DISABLED",
    "create_contract": "G8_28_CONTRACT_CREATION_DISABLED",
    "create_order": "G8_28_ORDER_CREATION_DISABLED",
    "submit_order": "G8_28_ORDER_SUBMISSION_DISABLED",
    "cancel_order": "G8_28_CANCELLATION_DISABLED",
    "modify_order": "G8_28_MODIFICATION_DISABLED",
}
ATTESTATION_FIELDS = {
    "engine","status","verified","order_object_design_independently_attested",
    "reason","checks","review_id","reviewer_id","design_sha256",
    "review_request_sha256","upstream_attestation_result_sha256",
    "attestation_sha256",*PERMISSION_FLAGS,"next_gate",
}
DESCRIBE_FIELDS = {
    "candidate_version": VERSION,
    "design_id": DESIGN_ID,
    "non_executable": True,
    "broker_mode": "PAPER",
    "host": "127.0.0.1",
    "port": 4002,
    "asset_type": "STK",
    "order_type": "LMT",
    "time_in_force": "DAY",
    "transmit": False,
    "ibkr_import_allowed": False,
    "network_allowed": False,
    **{name:False for name in PERMISSION_FLAGS},
}

def _blocked(reason):
    return {
        "engine":ENGINE_VERSION,"status":"BLOCKED","reason":reason,
        "candidate_validated":False,"design_attestation_verified":False,
        "candidate_source_sha256":None,"design_sha256":None,
        "design_attestation_sha256":None,
        **{name:False for name in PERMISSION_FLAGS},
        "next_gate":"REPAIR_G8_28_NONEXECUTABLE_CANDIDATE",
    }

def validate_candidate_source(source):
    if not isinstance(source,str) or not source or len(source)>20000:
        return False,"CANDIDATE_SOURCE_INVALID"
    try:
        tree=ast.parse(source)
    except (SyntaxError,ValueError):
        return False,"CANDIDATE_SOURCE_SYNTAX_INVALID"
    # Strict allowlist: only docstring, two literal assignments and one class.
    top=[node for node in tree.body
         if not (isinstance(node,ast.Expr) and isinstance(node.value,ast.Constant)
                 and isinstance(node.value.value,str))]
    if len(top)!=3:
        return False,"CANDIDATE_TOP_LEVEL_SHAPE_INVALID"
    expected_assignments=(("CANDIDATE_VERSION",VERSION),("DESIGN_ID",DESIGN_ID))
    for node,(name,value) in zip(top[:2],expected_assignments):
        if not (isinstance(node,ast.Assign) and len(node.targets)==1
                and isinstance(node.targets[0],ast.Name)
                and node.targets[0].id==name and isinstance(node.value,ast.Constant)
                and node.value.value==value):
            return False,"CANDIDATE_IDENTITY_INVALID"
    cls=top[2]
    if not (isinstance(cls,ast.ClassDef) and cls.name==CLASS_NAME
            and not cls.bases and not cls.keywords and not cls.decorator_list):
        return False,"CANDIDATE_CLASS_INVALID"
    methods=[node for node in cls.body if isinstance(node,ast.FunctionDef)]
    if len(methods)!=len(cls.body) or {node.name for node in methods}!=REQUIRED_METHODS:
        return False,"CANDIDATE_METHOD_SET_INVALID"
    if len(methods)!=len(REQUIRED_METHODS):
        return False,"CANDIDATE_DUPLICATE_METHOD"
    for method in methods:
        if method.decorator_list or method.returns is not None or method.args.defaults or method.args.kw_defaults:
            return False,"CANDIDATE_SIGNATURE_INVALID"
        name=method.name
        args=[a.arg for a in method.args.args]
        if name=="__init__":
            if args!=["self","design_attestation_sha256"] or method.args.vararg or method.args.kwarg:
                return False,"CANDIDATE_INIT_SIGNATURE_INVALID"
            body=method.body
            if len(body)!=1 or not isinstance(body[0],ast.Assign) or len(body[0].targets)!=1:
                return False,"CANDIDATE_INIT_BODY_INVALID"
            target=body[0].targets[0]
            if not (isinstance(target,ast.Attribute) and isinstance(target.value,ast.Name)
                    and target.value.id=="self" and target.attr=="_design_attestation_sha256"
                    and isinstance(body[0].value,ast.Name)
                    and body[0].value.id=="design_attestation_sha256"):
                return False,"CANDIDATE_INIT_BODY_INVALID"
        elif name=="describe":
            if args!=["self"] or method.args.vararg or method.args.kwarg or len(method.body)!=1 or not isinstance(method.body[0],ast.Return):
                return False,"CANDIDATE_DESCRIBE_INVALID"
            try:
                dictionary=method.body[0].value
                if not isinstance(dictionary,ast.Dict) or len(dictionary.keys)!=len(DESCRIBE_FIELDS):
                    return False,"CANDIDATE_DESCRIBE_INVALID"
                actual={}
                for key,value in zip(dictionary.keys,dictionary.values):
                    if not isinstance(key,ast.Constant) or not isinstance(key.value,str) or key.value in actual:
                        return False,"CANDIDATE_DESCRIBE_INVALID"
                    if isinstance(value,ast.Name) and value.id in ("CANDIDATE_VERSION","DESIGN_ID"):
                        actual[key.value]=VERSION if value.id=="CANDIDATE_VERSION" else DESIGN_ID
                    elif isinstance(value,ast.Constant) and type(value.value) in (str,int,bool):
                        actual[key.value]=value.value
                    else:
                        return False,"CANDIDATE_DESCRIBE_INVALID"
                if actual!=DESCRIBE_FIELDS:
                    return False,"CANDIDATE_DESCRIBE_PERMISSION_INVALID"
            except (TypeError,ValueError):
                return False,"CANDIDATE_DESCRIBE_INVALID"
        else:
            if args!=["self"] or not method.args.vararg or method.args.vararg.arg!="args" or not method.args.kwarg or method.args.kwarg.arg!="kwargs":
                return False,"CANDIDATE_BROKER_SIGNATURE_INVALID"
            if len(method.body)!=1 or not isinstance(method.body[0],ast.Raise):
                return False,"CANDIDATE_BROKER_METHOD_NOT_BLOCKED"
            exc=method.body[0].exc
            if not (isinstance(exc,ast.Call) and isinstance(exc.func,ast.Name)
                    and exc.func.id=="RuntimeError" and not exc.keywords
                    and len(exc.args)==1 and isinstance(exc.args[0],ast.Constant)
                    and exc.args[0].value==BLOCK_REASONS[name]):
                return False,"CANDIDATE_BROKER_METHOD_NOT_BLOCKED"
    return True,None

def evaluate_order_object_candidate(attestation,source,*,now=None):
    now=now or datetime.now(timezone.utc)
    if not isinstance(now,datetime) or now.tzinfo is None:
        return _blocked("CLOCK_INVALID")
    if not isinstance(attestation,dict) or set(attestation)!=ATTESTATION_FIELDS:
        return _blocked("SIGNED_DESIGN_ATTESTATION_SCHEMA_INVALID")
    checks=attestation.get("checks")
    if not (
        attestation.get("engine")==REVIEW_ENGINE
        and attestation.get("status")=="VERIFIED"
        and attestation.get("verified") is True
        and attestation.get("order_object_design_independently_attested") is True
        and attestation.get("reason")=="INDEPENDENT_IBKR_ORDER_OBJECT_DESIGN_ATTESTATION_VERIFIED"
        and attestation.get("next_gate")==REVIEW_NEXT_GATE
        and isinstance(checks,dict) and bool(checks)
        and all(v is True for v in checks.values())
        and all(attestation.get(k) is False for k in PERMISSION_FLAGS)
        and all(isinstance(attestation.get(k),str) and re.fullmatch(r"[0-9a-f]{64}",attestation[k])
                for k in ("design_sha256","review_request_sha256","upstream_attestation_result_sha256","attestation_sha256"))
    ):
        return _blocked("SIGNED_DESIGN_ATTESTATION_NOT_VERIFIED")
    safe,reason=validate_candidate_source(source)
    if not safe:
        return _blocked(reason)
    return {
        "engine":ENGINE_VERSION,
        "status":"NON_EXECUTABLE_ORDER_OBJECT_CANDIDATE_VALIDATED",
        "reason":"INDEPENDENT_CANDIDATE_REVIEW_REQUIRED",
        "candidate_validated":True,"design_attestation_verified":True,
        "candidate_source_sha256":hashlib.sha256(source.encode("utf-8")).hexdigest(),
        "design_sha256":attestation["design_sha256"],
        "design_attestation_sha256":attestation["attestation_sha256"],
        **{name:False for name in PERMISSION_FLAGS},
        "next_gate":NEXT_GATE,
    }
