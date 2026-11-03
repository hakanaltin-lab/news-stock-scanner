#!/usr/bin/env python3
"""Fixed-path G8.26 design reviewer handoff, unsigned and non-executable."""
from __future__ import annotations
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from engines.gateway_readonly_attestation_verifier import _repository_is_clean, _load_json_bytes
from scripts.gateway_review_package import read_trusted_runtime_evidence_json
from scripts.ibkr_paper_probe import write_runtime_evidence_atomic
from engines.ibkr_order_object_design_handoff import evaluate_order_object_design_handoff

DESIGN=ROOT/"config/ibkr_order_object_materializer_design_v1.json"
UPSTREAM=ROOT/"runtime/aurora_g6_offline_materializer_attestation/latest.json"
OUTPUT=ROOT/"runtime/aurora_g6_order_object_design_handoff/latest.json"

def main():
    if _repository_is_clean(ROOT) is not True:
        print('BLOCKED: repository not clean')
        return 2
    try:
        design=_load_json_bytes(DESIGN.read_bytes())
        upstream=read_trusted_runtime_evidence_json(UPSTREAM)
    except (OSError,TypeError,ValueError,UnicodeDecodeError):
        print('BLOCKED: trusted input unavailable')
        return 2
    if upstream is None or _repository_is_clean(ROOT) is not True:
        print('BLOCKED: upstream evidence not trusted')
        return 2
    result=evaluate_order_object_design_handoff(design,upstream)
    try:
        write_runtime_evidence_atomic(OUTPUT,result)
    except (OSError,RuntimeError,ValueError):
        print('BLOCKED: output write failed')
        return 2
    print(json.dumps(result,sort_keys=True,indent=2))
    return 0 if result["ready_for_independent_review"] is True else 2

if __name__=="__main__": raise SystemExit(main())
