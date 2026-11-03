#!/usr/bin/env python3
"""G8.29 fixed-path non-attesting candidate handoff; never imports candidate."""
from __future__ import annotations
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from engines.gateway_readonly_attestation_verifier import _repository_is_clean
from engines.ibkr_order_object_candidate_handoff import evaluate_order_object_candidate_handoff
from scripts.gateway_review_package import read_trusted_runtime_evidence_json
from scripts.ibkr_paper_probe import write_runtime_evidence_atomic

CANDIDATE_SOURCE=ROOT/"broker_engine/ibkr_order_object_materializer_candidate.py"
CANDIDATE_REVIEW=ROOT/"runtime/aurora_g6_order_object_candidate/latest.json"
DESIGN_ATTESTATION=ROOT/"runtime/aurora_g6_order_object_design_attestation/latest.json"
OUTPUT=ROOT/"runtime/aurora_g6_order_object_candidate_handoff/latest.json"

def main():
    if _repository_is_clean(ROOT) is not True:
        print("BLOCKED: repository not clean")
        return 2
    try:
        source=CANDIDATE_SOURCE.read_text(encoding="utf-8")
    except (OSError,UnicodeDecodeError):
        print("BLOCKED: unreadable candidate source")
        return 2
    candidate_review=read_trusted_runtime_evidence_json(CANDIDATE_REVIEW)
    attestation=read_trusted_runtime_evidence_json(DESIGN_ATTESTATION)
    if not candidate_review or not attestation or _repository_is_clean(ROOT) is not True:
        print("BLOCKED: untrusted runtime inputs")
        return 2
    result=evaluate_order_object_candidate_handoff(candidate_review,source,attestation)
    try:
        write_runtime_evidence_atomic(OUTPUT,result)
    except (OSError,RuntimeError,ValueError):
        print("BLOCKED: runtime output write failed")
        return 2
    print(json.dumps(result,sort_keys=True,indent=2))
    return 0 if result.get("ready_for_independent_review") is True else 2
if __name__=="__main__":raise SystemExit(main())
