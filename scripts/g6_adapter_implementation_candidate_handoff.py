#!/usr/bin/env python3
"""Build the G8.20 non-attesting implementation-candidate reviewer handoff."""

from __future__ import annotations

import json
from pathlib import Path
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from engines.paper_adapter_implementation_candidate_handoff import (
    evaluate_candidate_review_handoff,
)
from scripts.g6_adapter_implementation_candidate_review import (
    _read_fixed_candidate_source,
    build_installed_implementation_candidate_review,
)
from scripts.ibkr_paper_probe import (
    write_runtime_evidence_atomic,
)


DEFAULT_OUTPUT = (
    REPOSITORY_ROOT
    / "runtime/aurora_g6_implementation_candidate_handoff/latest.json"
)


def _blocked(reason):
    return {
        "engine": "AURORA G8.20 Implementation Candidate Handoff CLI",
        "status": "BLOCKED",
        "reason": reason,
        "ready_for_independent_candidate_review": False,
        "candidate_revalidated": False,
        "candidate_attestation_verified": False,
        "operator_asserts_candidate_safe": False,
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
        "next_gate": "REPAIR_IMPLEMENTATION_CANDIDATE_REVIEW_HANDOFF",
    }


def build_installed_candidate_review_handoff():
    candidate_review = (
        build_installed_implementation_candidate_review()
    )
    if (
        not isinstance(candidate_review, dict)
        or candidate_review.get(
            "candidate_validated"
        )
        is not True
    ):
        return _blocked(
            "G8_19_IMPLEMENTATION_CANDIDATE_NOT_VALIDATED"
        )

    candidate_source = (
        _read_fixed_candidate_source()
    )
    if candidate_source is None:
        return _blocked(
            "CANDIDATE_SOURCE_UNAVAILABLE"
        )

    return evaluate_candidate_review_handoff(
        candidate_review,
        candidate_source,
    )


def main():
    result = build_installed_candidate_review_handoff()

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
            "IMPLEMENTATION_CANDIDATE_HANDOFF_WRITE_FAILED"
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
            "ready_for_independent_candidate_review"
        )
        is True
        else 2
    )


if __name__ == "__main__":
    raise SystemExit(main())
