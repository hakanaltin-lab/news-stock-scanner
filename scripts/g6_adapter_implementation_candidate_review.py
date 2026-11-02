#!/usr/bin/env python3
"""Validate the fixed G8.19 non-executable adapter implementation candidate."""

from __future__ import annotations

import json
from pathlib import Path
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from engines.gateway_readonly_attestation_verifier import (
    _repository_is_clean,
)
from engines.paper_adapter_implementation_candidate_review import (
    evaluate_implementation_candidate,
)
from scripts.gateway_review_package import (
    read_trusted_runtime_evidence_json,
)
from scripts.ibkr_paper_probe import (
    write_runtime_evidence_atomic,
)


DEFAULT_DESIGN_ATTESTATION = (
    REPOSITORY_ROOT
    / "runtime/aurora_g6_design_attestation/latest.json"
)
DEFAULT_CANDIDATE_PATH = (
    REPOSITORY_ROOT
    / "broker_engine/ibkr_paper_adapter_implementation_candidate.py"
)
DEFAULT_OUTPUT = (
    REPOSITORY_ROOT
    / "runtime/aurora_g6_implementation_candidate/latest.json"
)


def _blocked(reason):
    return {
        "engine": "AURORA G8.19 Implementation Candidate Review CLI",
        "status": "BLOCKED",
        "reason": reason,
        "candidate_validated": False,
        "design_attestation_verified": False,
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
        "next_gate": "REPAIR_NON_EXECUTABLE_IMPLEMENTATION_CANDIDATE",
    }


def _read_fixed_candidate_source():
    try:
        path = DEFAULT_CANDIDATE_PATH.resolve(
            strict=True
        )
        root = REPOSITORY_ROOT.resolve(
            strict=True
        )
    except OSError:
        return None

    expected = (
        root
        / "broker_engine/ibkr_paper_adapter_implementation_candidate.py"
    )
    if path != expected:
        return None

    try:
        return path.read_text(
            encoding="utf-8"
        )
    except (
        OSError,
        UnicodeDecodeError,
    ):
        return None


def build_installed_implementation_candidate_review():
    clean_before = _repository_is_clean(
        REPOSITORY_ROOT
    )
    if clean_before is not True:
        return _blocked(
            "REPOSITORY_NOT_CLEAN"
        )

    design_attestation = (
        read_trusted_runtime_evidence_json(
            DEFAULT_DESIGN_ATTESTATION
        )
    )
    candidate_source = (
        _read_fixed_candidate_source()
    )

    clean_after = _repository_is_clean(
        REPOSITORY_ROOT
    )

    if (
        not design_attestation
        or candidate_source is None
        or clean_after is not True
    ):
        return _blocked(
            "CANDIDATE_REVIEW_INPUT_UNTRUSTED"
        )

    return evaluate_implementation_candidate(
        design_attestation,
        candidate_source,
    )


def main():
    result = (
        build_installed_implementation_candidate_review()
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
            "IMPLEMENTATION_CANDIDATE_REVIEW_WRITE_FAILED"
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
        if result.get("candidate_validated") is True
        else 2
    )


if __name__ == "__main__":
    raise SystemExit(main())
