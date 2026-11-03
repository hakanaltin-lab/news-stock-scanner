#!/usr/bin/env python3
"""Build the G8.23 non-attesting offline materializer reviewer handoff."""

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
from engines.offline_order_request_materializer_handoff import (
    evaluate_materializer_review_handoff,
)
from scripts.ibkr_paper_probe import write_runtime_evidence_atomic


DESIGN_PATH = (
    REPOSITORY_ROOT
    / "config/offline_order_request_materializer_design_v1.json"
)
MATERIALIZER_PATH = (
    REPOSITORY_ROOT
    / "engines/offline_order_request_materializer.py"
)
CLI_PATH = (
    REPOSITORY_ROOT
    / "scripts/build_offline_order_request_preview.py"
)
DEFAULT_OUTPUT = (
    REPOSITORY_ROOT
    / "runtime/aurora_g6_offline_materializer_handoff/latest.json"
)


def _blocked(reason):
    return {
        "engine": "AURORA G8.23 Offline Materializer Handoff CLI",
        "status": "BLOCKED",
        "reason": reason,
        "ready_for_independent_materializer_review": False,
        "design_revalidated": False,
        "materializer_source_revalidated": False,
        "cli_source_revalidated": False,
        "operator_asserts_materializer_safe": False,
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
        "next_gate": "REPAIR_OFFLINE_MATERIALIZER_REVIEW_HANDOFF",
    }


def build_installed_materializer_review_handoff():
    if _repository_is_clean(REPOSITORY_ROOT) is not True:
        return _blocked("REPOSITORY_NOT_CLEAN")

    try:
        design = _load_json_bytes(DESIGN_PATH.read_bytes())
        materializer_source = MATERIALIZER_PATH.read_text(encoding="utf-8")
        cli_source = CLI_PATH.read_text(encoding="utf-8")
    except (
        OSError,
        UnicodeDecodeError,
        ValueError,
        TypeError,
    ):
        return _blocked("OFFLINE_MATERIALIZER_REVIEW_INPUT_UNAVAILABLE")

    if _repository_is_clean(REPOSITORY_ROOT) is not True:
        return _blocked("REPOSITORY_CHANGED_DURING_REVIEW_HANDOFF")

    return evaluate_materializer_review_handoff(
        design,
        materializer_source,
        cli_source,
    )


def main():
    result = build_installed_materializer_review_handoff()
    try:
        write_runtime_evidence_atomic(DEFAULT_OUTPUT, result)
    except (OSError, RuntimeError, ValueError):
        result = _blocked("OFFLINE_MATERIALIZER_HANDOFF_WRITE_FAILED")

    print(json.dumps(result, indent=2, sort_keys=True))
    return (
        0
        if result.get("ready_for_independent_materializer_review") is True
        else 2
    )


if __name__ == "__main__":
    raise SystemExit(main())
