#!/usr/bin/env python3
"""G8.30: verify fixed-path independently signed review; no broker imports."""
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
from engines.ibkr_order_object_candidate_attestation import (
    canonical_signed_payload,evaluate_signed_order_object_candidate_attestation,
)
from scripts.gateway_review_package import read_trusted_runtime_evidence_json
from scripts.ibkr_paper_probe import write_runtime_evidence_atomic

POLICY=Path("/etc/aurora/order-object-candidate-review-policy.json")
PUBKEY=Path("/etc/aurora/order-object-candidate-reviewer-ed25519.pem")
ARTIFACT=Path("/var/lib/aurora/order-object-candidate-review-attestation/latest.json")
HANDOFF=ROOT/"runtime/aurora_g6_order_object_candidate_handoff/latest.json"
CANDIDATE_REVIEW=ROOT/"runtime/aurora_g6_order_object_candidate/latest.json"
DESIGN_ATTESTATION=ROOT/"runtime/aurora_g6_order_object_design_attestation/latest.json"
SOURCE=ROOT/"broker_engine/ibkr_order_object_materializer_candidate.py"
OUTPUT=ROOT/"runtime/aurora_g6_order_object_candidate_attestation/latest.json"

def main():
    for path,size,validator in (
        (POLICY,8192,_trusted_root_file),
        (PUBKEY,8192,_trusted_root_file),
        (ARTIFACT,32768,_artifact_file_safe),
    ):
        safe,_=validator(path,max_bytes=size)
        if not safe:
            print("BLOCKED: untrusted signed review inputs")
            return 2
    if _repository_is_clean(ROOT) is not True:
        print("BLOCKED: dirty repository")
        return 2
    try:
        policy=_load_json_bytes(POLICY.read_bytes())
        pubkey=PUBKEY.read_bytes()
        artifact=_load_json_bytes(ARTIFACT.read_bytes())
        source=SOURCE.read_text(encoding="utf-8")
    except (OSError,TypeError,ValueError,UnicodeDecodeError):
        print("BLOCKED: invalid review inputs")
        return 2
    handoff=read_trusted_runtime_evidence_json(HANDOFF)
    candidate_review=read_trusted_runtime_evidence_json(CANDIDATE_REVIEW)
    design_attestation=read_trusted_runtime_evidence_json(DESIGN_ATTESTATION)
    if not handoff or not candidate_review or not design_attestation or _repository_is_clean(ROOT) is not True:
        print("BLOCKED: missing trusted runtime evidence")
        return 2
    payload=canonical_signed_payload(artifact)
    signature=decode_signature(artifact.get("signature_b64") if isinstance(artifact,dict) else None)
    signature_valid=(
        payload is not None and signature is not None
        and _verify_ed25519_signature(pubkey,payload,signature)
    )
    result=evaluate_signed_order_object_candidate_attestation(
        artifact,policy,pubkey,signature_valid,handoff,source,
        candidate_review,design_attestation,True,
    )
    try:
        write_runtime_evidence_atomic(OUTPUT,result)
    except (OSError,RuntimeError,ValueError):
        print("BLOCKED: evidence write failed")
        return 2
    print(json.dumps(result,sort_keys=True,indent=2))
    return 0 if result.get("verified") is True else 2
if __name__=="__main__":raise SystemExit(main())
