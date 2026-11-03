#!/usr/bin/env python3
"""Evaluate the fixed G8.25 non-executable IBKR Order-object design."""

from __future__ import annotations

import json
from pathlib import Path
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from engines.gateway_readonly_attestation_verifier import (
    _load_json_bytes,
    _repository_is_clean,
)
from engines.ibkr_order_object_materializer_design import (
    evaluate_ibkr_order_object_design,
)
from scripts.gateway_review_package import read_trusted_runtime_evidence_json
from scripts.ibkr_paper_probe import write_runtime_evidence_atomic


DEFAULT_DESIGN_PATH = (
    REPOSITORY_ROOT
    / "config/ibkr_order_object_materializer_design_v1.json"
)
DEFAULT_MATERIALIZER_ATTESTATION = (
    REPOSITORY_ROOT
    / "runtime/aurora_g6_offline_materializer_attestation/latest.json"
)
DEFAULT_OUTPUT = (
    REPOSITORY_ROOT
    / "runtime/aurora_g6_ibkr_order_object_design/latest.json"
)


def _blocked(reason):
    return {
        "engine": "AURORA G8.25 IBKR Order Object Design CLI",
        "status": "BLOCKED",
        "reason": reason,
        "design_validated": False,
        "materializer_attestation_verified": False,
        "implementation_allowed": False,
        "connection_allowed": False,
        "broker_request_materialization_allowed": False,
        "broker_order_object_allowed": False,
        "automatic_retry_allowed": False,
        "automatic_cancel_allowed": False,
        "automatic_modify_allowed": False,
        "broker_submission_allowed": False,
        "paper_order_submission_allowed": False,
        "live_execution_allowed": False,
        "automatic_promotion_allowed": False,
        "real_money_trading_allowed": False,
        "next_gate": "REPAIR_NON_EXECUTABLE_IBKR_ORDER_OBJECT_DESIGN",
    }


def build_installed_ibkr_order_object_design():
    if _repository_is_clean(REPOSITORY_ROOT) is not True:
        return _blocked("REPOSITORY_NOT_CLEAN")

    try:
        design = _load_json_bytes(DEFAULT_DESIGN_PATH.read_bytes())
    except (
        OSError,
        UnicodeDecodeError,
        ValueError,
        TypeError,
    ):
        return _blocked("IBKR_ORDER_OBJECT_DESIGN_PARSE_FAILED")

    attestation = read_trusted_runtime_evidence_json(
        DEFAULT_MATERIALIZER_ATTESTATION
    )
    if (
        not attestation
        or _repository_is_clean(REPOSITORY_ROOT) is not True
    ):
        return _blocked("MATERIALIZER_ATTESTATION_RUNTIME_EVIDENCE_UNTRUSTED")

    return evaluate_ibkr_order_object_design(
        design,
        attestation,
    )


def main():
    result = build_installed_ibkr_order_object_design()
    try:
        write_runtime_evidence_atomic(DEFAULT_OUTPUT, result)
    except (OSError, RuntimeError, ValueError):
        result = _blocked("IBKR_ORDER_OBJECT_DESIGN_WRITE_FAILED")

    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("design_validated") is True else 2


if __name__ == "__main__":
    raise SystemExit(main())
