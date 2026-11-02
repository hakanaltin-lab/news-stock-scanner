#!/usr/bin/env python3
"""Validate one fresh G2 pre-review run without authorizing execution."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from uuid import UUID

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from engines.gateway_attestation_handoff import (
    build_installed_reviewer_handoff,
)
from scripts.gateway_review_package import (
    RUNTIME_BOUND_PACKAGE_SCHEMA_VERSION,
    RUNTIME_BOUND_PACKAGE_TYPE,
    build_runtime_bound_review_package,
    load_installed_g2_diagnostic_proof,
)


ENGINE_VERSION = "AURORA G8.5 G2 Pre-Review Status"

_PERMISSION_FLAGS = (
    "broker_submission_allowed",
    "paper_order_submission_allowed",
    "live_execution_allowed",
    "automatic_promotion_allowed",
    "real_money_trading_allowed",
)


def _uuid4(value):
    text = str(value or "").strip()
    try:
        parsed = UUID(text)
    except (ValueError, AttributeError):
        return None
    if parsed.version != 4 or str(parsed) != text:
        return None
    return text


def _hex_digest(value):
    text = str(value or "").strip().lower()
    if (
        len(text) != 64
        or any(
            character not in "0123456789abcdef"
            for character in text
        )
    ):
        return None
    return text


def _blocked(reason, expected_run_id=None):
    return {
        "engine": ENGINE_VERSION,
        "status": "BLOCKED",
        "evidence_run_id": expected_run_id,
        "review_package_type": None,
        "review_package_schema_version": None,
        "g2_diagnostic_proof_sha256": None,
        "handoff_request_sha256": None,
        "gcp_instance_id": None,
        "g0_runtime_proof_sha256": None,
        "next_action": "STOP_AND_REPAIR_PRE_REVIEW_EVIDENCE",
        "human_action_required": True,
        "failure_reasons": [reason],
        "broker_submission_allowed": False,
        "paper_order_submission_allowed": False,
        "live_execution_allowed": False,
        "automatic_promotion_allowed": False,
        "real_money_trading_allowed": False,
    }


def evaluate_pre_review_status(
    expected_run_id,
    g2_proof,
    handoff_result,
    *,
    review_package_result=None,
    now=None,
):
    expected_run_id = _uuid4(
        expected_run_id
    )
    if expected_run_id is None:
        return _blocked(
            "EXPECTED_EVIDENCE_RUN_ID_INVALID"
        )

    if not isinstance(g2_proof, dict):
        return _blocked(
            "G2_DIAGNOSTIC_PROOF_INVALID",
            expected_run_id,
        )

    if (
        _uuid4(
            g2_proof.get(
                "evidence_run_id"
            )
        )
        !=
        expected_run_id
    ):
        return _blocked(
            "G2_DIAGNOSTIC_EVIDENCE_RUN_MISMATCH",
            expected_run_id,
        )

    package = (
        review_package_result
        if review_package_result is not None
        else build_runtime_bound_review_package(
            handoff_result,
            g2_proof,
            now=now,
        )
    )

    if not isinstance(package, dict):
        return _blocked(
            "REVIEW_PACKAGE_INVALID",
            expected_run_id,
        )

    if not all(
        package.get(name) is False
        for name in _PERMISSION_FLAGS
    ):
        return _blocked(
            "EXECUTION_PERMISSION_INVARIANT_FAILED",
            expected_run_id,
        )

    summary = package.get(
        "g2_diagnostic_summary"
    )
    if not isinstance(summary, dict):
        return _blocked(
            "G2_DIAGNOSTIC_SUMMARY_INVALID",
            expected_run_id,
        )

    package_ready = (
        package.get("status")
        == "READY_FOR_INDEPENDENT_REVIEW_PACKAGE"
        and package.get("package_type")
        == RUNTIME_BOUND_PACKAGE_TYPE
        and package.get("package_schema_version")
        == RUNTIME_BOUND_PACKAGE_SCHEMA_VERSION
        and package.get("ready_for_independent_review")
        is True
        and package.get("attestation_verified")
        is False
        and package.get(
            "gateway_read_only_configuration_independently_attested"
        )
        is False
        and package.get("failure_reasons") == []
        and _uuid4(
            summary.get(
                "evidence_run_id"
            )
        )
        ==
        expected_run_id
    )
    if not package_ready:
        reason = "REVIEW_PACKAGE_NOT_READY"
        failures = package.get(
            "failure_reasons"
        )
        if (
            isinstance(failures, list)
            and len(failures) == 1
            and isinstance(failures[0], str)
            and failures[0]
        ):
            reason = failures[0]
        return _blocked(
            reason,
            expected_run_id,
        )

    g2_digest = _hex_digest(
        package.get(
            "g2_diagnostic_proof_sha256"
        )
    )
    handoff_digest = _hex_digest(
        package.get(
            "handoff_request_sha256"
        )
    )
    g0_digest = _hex_digest(
        summary.get(
            "g0_runtime_proof_sha256"
        )
    )
    instance_id = str(
        summary.get(
            "gcp_instance_id"
        )
        or
        ""
    ).strip()

    if (
        g2_digest is None
        or handoff_digest is None
        or g0_digest is None
        or not instance_id.isdigit()
        or not 6 <= len(instance_id) <= 30
        or instance_id[0] == "0"
    ):
        return _blocked(
            "PRE_REVIEW_BINDING_INVALID",
            expected_run_id,
        )

    return {
        "engine": ENGINE_VERSION,
        "status": "READY_FOR_INDEPENDENT_REVIEW",
        "evidence_run_id": expected_run_id,
        "review_package_type": RUNTIME_BOUND_PACKAGE_TYPE,
        "review_package_schema_version": (
            RUNTIME_BOUND_PACKAGE_SCHEMA_VERSION
        ),
        "g2_diagnostic_proof_sha256": g2_digest,
        "handoff_request_sha256": handoff_digest,
        "gcp_instance_id": instance_id,
        "g0_runtime_proof_sha256": g0_digest,
        "next_action": (
            "COMPLETE_INDEPENDENT_GATEWAY_READ_ONLY_REVIEW"
        ),
        "human_action_required": True,
        "failure_reasons": [],
        "broker_submission_allowed": False,
        "paper_order_submission_allowed": False,
        "live_execution_allowed": False,
        "automatic_promotion_allowed": False,
        "real_money_trading_allowed": False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--expected-run-id",
        required=True,
    )
    args = parser.parse_args(argv)

    result = evaluate_pre_review_status(
        args.expected_run_id,
        load_installed_g2_diagnostic_proof(),
        build_installed_reviewer_handoff(
            REPOSITORY_ROOT
        ),
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
        if result["status"]
        == "READY_FOR_INDEPENDENT_REVIEW"
        else 2
    )


if __name__ == "__main__":
    raise SystemExit(main())
