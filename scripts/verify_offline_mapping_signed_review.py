#!/usr/bin/env python3
"""G8.33 verified signed mapping review, fixed paths and offline only."""
from __future__ import annotations
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from engines.gateway_readonly_attestation_verifier import (
    _artifact_file_safe,_trusted_root_file,_load_json_bytes,
    _repository_is_clean,_verify_ed25519_signature,
)
from engines.paper_adapter_source_attestation import decode_signature
from engines.ibkr_offline_mapping_signed_review import (
    canonical_signed_payload,evaluate_signed_offline_mapping_review,
)
from scripts.gateway_review_package import read_trusted_runtime_evidence_json
from scripts.ibkr_paper_probe import write_runtime_evidence_atomic

POLICY=Path("/etc/aurora/offline-mapping-review-policy.json")
PUBKEY=Path("/etc/aurora/offline-mapping-reviewer-ed25519.pem")
ARTIFACT=Path("/var/lib/aurora/offline-mapping-review-attestation/latest.json")
DESIGN=ROOT/"config/ibkr_order_object_materializer_design_v1.json"
CANDIDATE_ATTESTATION=ROOT/"runtime/aurora_g6_order_object_candidate_attestation/latest.json"
PREVIEW=ROOT/"runtime/aurora_g6_offline_order_request/latest.json"
MAPPING_RESULT=ROOT/"runtime/aurora_g6_offline_mapping/latest.json"
HANDOFF=ROOT/"runtime/aurora_g6_offline_mapping_handoff/latest.json"
OUTPUT=ROOT/"runtime/aurora_g6_offline_mapping_attestation/latest.json"

def main():
    for path,size,validate in (
        (POLICY,8192,_trusted_root_file),
        (PUBKEY,8192,_trusted_root_file),
        (ARTIFACT,32768,_artifact_file_safe),
    ):
        safe,_=validate(path,max_bytes=size)
        if not safe:
            print("BLOCKED: untrusted independent reviewer material")
            return 2
    if _repository_is_clean(ROOT) is not True:
        print("BLOCKED: repository not clean")
        return 2
    try:
        policy=_load_json_bytes(POLICY.read_bytes())
        pubkey=PUBKEY.read_bytes()
        signed=_load_json_bytes(ARTIFACT.read_bytes())
        design=_load_json_bytes(DESIGN.read_bytes())
    except (OSError,TypeError,ValueError,UnicodeDecodeError):
        print("BLOCKED: reviewer material invalid")
        return 2
    handoff=read_trusted_runtime_evidence_json(HANDOFF)
    candidate=read_trusted_runtime_evidence_json(CANDIDATE_ATTESTATION)
    preview=read_trusted_runtime_evidence_json(PREVIEW)
    mapping=read_trusted_runtime_evidence_json(MAPPING_RESULT)
    if not all(isinstance(x,dict) for x in (handoff,candidate,preview,mapping)):
        print("BLOCKED: missing trusted offline evidence")
        return 2
    if _repository_is_clean(ROOT) is not True:
        print("BLOCKED: changed repository")
        return 2
    payload=canonical_signed_payload(signed)
    signature=decode_signature(signed.get("signature_b64") if isinstance(signed,dict) else None)
    signature_valid=(payload is not None and signature is not None
                     and _verify_ed25519_signature(pubkey,payload,signature))
    result=evaluate_signed_offline_mapping_review(
        signed,policy,pubkey,signature_valid,
        handoff,design,candidate,preview,mapping,True,
    )
    try:
        write_runtime_evidence_atomic(OUTPUT,result)
    except (OSError,RuntimeError,ValueError):
        print("BLOCKED: runtime output write failed")
        return 2
    print(json.dumps(result,indent=2,sort_keys=True))
    return 0 if result.get("verified") is True else 2

if __name__=="__main__":raise SystemExit(main())
