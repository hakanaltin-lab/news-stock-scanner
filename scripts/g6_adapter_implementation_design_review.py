#!/usr/bin/env python3
"""Build the G8.16 non-executable adapter implementation-design review state."""

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
from engines.paper_adapter_implementation_design import (
    evaluate_implementation_design,
)
from scripts.g6_adapter_source_review import (
    _read_fixed_tracked_source,
)
from scripts.gateway_review_package import (
    read_trusted_runtime_evidence_json,
)
from scripts.ibkr_paper_probe import (
    write_runtime_evidence_atomic,
)


DEFAULT_DESIGN_PATH = (
    REPOSITORY_ROOT
    / "config/ibkr_paper_adapter_implementation_design_v1.json"
)
DEFAULT_SOURCE_ATTESTATION = (
    REPOSITORY_ROOT
    / "runtime/aurora_g6_source_attestation/latest.json"
)
DEFAULT_OUTPUT = (
    REPOSITORY_ROOT
    / "runtime/aurora_g6_implementation_design/latest.json"
)


def _blocked(reason):
    return {
        "engine": "AURORA G8.16 Adapter Implementation Design CLI",
        "status": "BLOCKED",
        "reason": reason,
        "design_validated": False,
        "source_attestation_verified": False,
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
        "next_gate": "REPAIR_NON_EXECUTABLE_IMPLEMENTATION_DESIGN",
    }


def build_installed_implementation_design_review():
    clean_before = _repository_is_clean(
        REPOSITORY_ROOT
    )
    if clean_before is not True:
        return _blocked(
            "REPOSITORY_NOT_CLEAN"
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

    source_attestation = (
        read_trusted_runtime_evidence_json(
            DEFAULT_SOURCE_ATTESTATION
        )
    )
    if not source_attestation:
        return _blocked(
            "SOURCE_ATTESTATION_EVIDENCE_UNAVAILABLE"
        )

    source_text = _read_fixed_tracked_source()
    clean_after = _repository_is_clean(
        REPOSITORY_ROOT
    )

    if (
        source_text is None
        or clean_after is not True
    ):
        return _blocked(
            "TRACKED_SOURCE_OR_REPOSITORY_STATE_UNTRUSTED"
        )

    return evaluate_implementation_design(
        design,
        source_attestation,
        source_text,
    )


def main():
    result = (
        build_installed_implementation_design_review()
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
            "IMPLEMENTATION_DESIGN_REVIEW_WRITE_FAILED"
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
        if result.get("design_validated") is True
        else 2
    )


if __name__ == "__main__":
    raise SystemExit(main())
