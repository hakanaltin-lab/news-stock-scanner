#!/usr/bin/env python3
"""Build the G8.17 non-attesting implementation-design reviewer handoff."""

from __future__ import annotations

import json
from pathlib import Path
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from engines.gateway_readonly_attestation_verifier import (
    _load_json_bytes,
)
from engines.paper_adapter_implementation_design_handoff import (
    evaluate_implementation_design_handoff,
)
from scripts.g6_adapter_implementation_design_review import (
    DEFAULT_DESIGN_PATH,
    build_installed_implementation_design_review,
)
from scripts.ibkr_paper_probe import (
    write_runtime_evidence_atomic,
)


DEFAULT_OUTPUT = (
    REPOSITORY_ROOT
    / "runtime/aurora_g6_implementation_design_handoff/latest.json"
)


def _blocked(reason):
    return {
        "engine": "AURORA G8.17 Adapter Implementation Design Handoff CLI",
        "status": "BLOCKED",
        "reason": reason,
        "ready_for_independent_design_review": False,
        "design_revalidated": False,
        "design_attestation_verified": False,
        "operator_asserts_design_safe": False,
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
        "next_gate": "REPAIR_IMPLEMENTATION_DESIGN_REVIEW_HANDOFF",
    }


def build_installed_implementation_design_handoff():
    design_review = (
        build_installed_implementation_design_review()
    )
    if (
        not isinstance(design_review, dict)
        or design_review.get("design_validated")
        is not True
    ):
        return _blocked(
            "G8_16_IMPLEMENTATION_DESIGN_NOT_VALIDATED"
        )

    try:
        design = _load_json_bytes(
            DEFAULT_DESIGN_PATH.read_bytes()
        )
    except (
        OSError,
        UnicodeDecodeError,
        ValueError,
        TypeError,
    ):
        return _blocked(
            "IMPLEMENTATION_DESIGN_PARSE_FAILED"
        )

    return evaluate_implementation_design_handoff(
        design_review,
        design,
    )


def main():
    result = (
        build_installed_implementation_design_handoff()
    )

    try:
        write_runtime_evidence_atomic(
            DEFAULT_OUTPUT,
            result,
        )
    except (
        OSError,
        RuntimeError,
        ValueError,
    ):
        result = _blocked(
            "IMPLEMENTATION_DESIGN_HANDOFF_WRITE_FAILED"
        )

    print(
        json.dumps(
            result,
            indent=2,
            sort_keys=True,
        )
    )

    return (
        0
        if result.get(
            "ready_for_independent_design_review"
        )
        is True
        else 2
    )


if __name__ == "__main__":
    raise SystemExit(main())
