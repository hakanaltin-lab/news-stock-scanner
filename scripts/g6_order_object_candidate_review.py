#!/usr/bin/env python3
"""G8.28 AST-only candidate review; never imports candidate."""
from __future__ import annotations
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from engines.gateway_readonly_attestation_verifier import _repository_is_clean
from engines.ibkr_order_object_candidate_review import evaluate_order_object_candidate
from scripts.gateway_review_package import read_trusted_runtime_evidence_json
from scripts.ibkr_paper_probe import write_runtime_evidence_atomic
ATTESTATION=ROOT/"runtime/aurora_g6_order_object_design_attestation/latest.json"
CANDIDATE=ROOT/"broker_engine/ibkr_order_object_materializer_candidate.py"
OUTPUT=ROOT/"runtime/aurora_g6_order_object_candidate/latest.json"
def main():
    if _repository_is_clean(ROOT) is not True:
        print("BLOCKED: repository not clean")
        return 2
    attestation=read_trusted_runtime_evidence_json(ATTESTATION)
    try:
        source=CANDIDATE.read_text(encoding="utf-8")
    except (OSError,UnicodeDecodeError):
        print("BLOCKED: candidate source unreadable")
        return 2
    if attestation is None or _repository_is_clean(ROOT) is not True:
        print("BLOCKED: untrusted signed design evidence")
        return 2
    result=evaluate_order_object_candidate(attestation,source)
    try:
        write_runtime_evidence_atomic(OUTPUT,result)
    except (OSError,RuntimeError,ValueError):
        print("BLOCKED: evidence write failed")
        return 2
    print(json.dumps(result,indent=2,sort_keys=True))
    return 0 if result.get("candidate_validated") is True else 2
if __name__=="__main__":raise SystemExit(main())
