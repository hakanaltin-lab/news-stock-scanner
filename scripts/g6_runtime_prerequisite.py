#!/usr/bin/env python3
"""Build the trusted G8.12/G6 Paper connector runtime prerequisite artifact.

This command is review-only. It cannot connect to IBKR, create an order object,
materialize a broker request, or submit/cancel/modify an order.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from engines.gateway_readonly_attestation_verifier import (
    verify_installed_gateway_readonly_attestation,
)
from engines.paper_connector_review_prerequisite import (
    evaluate_g6_runtime_prerequisite,
)
from scripts.gateway_review_package import (
    read_trusted_runtime_evidence_json,
)
from scripts.ibkr_paper_probe import (
    write_runtime_evidence_atomic,
)


DEFAULT_G5_VALIDATION = (
    "runtime/aurora_g5_authorization/latest.json"
)
DEFAULT_COMPLETION_STATUS = (
    "runtime/aurora_project_status/latest.json"
)
DEFAULT_G4_SHADOW = (
    "runtime/aurora_g4_shadow/latest.json"
)
DEFAULT_G2_PROOF = (
    "runtime/ibkr_paper_read_only/latest.json"
)
DEFAULT_OUTPUT = (
    "runtime/aurora_g6_runtime_prerequisite/latest.json"
)


def _blocked(reason):
    return {
        "engine": (
            "AURORA G8.12 G6 Paper Connector Runtime Prerequisite CLI"
        ),
        "status": "BLOCKED",
        "reason": reason,
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
        "next_gate": "REPAIR_G6_RUNTIME_PREREQUISITES",
    }


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--authorization",
        required=True,
    )
    parser.add_argument(
        "--g5-validation",
        default=DEFAULT_G5_VALIDATION,
    )
    parser.add_argument(
        "--completion-status",
        default=DEFAULT_COMPLETION_STATUS,
    )
    parser.add_argument(
        "--g4-shadow",
        default=DEFAULT_G4_SHADOW,
    )
    parser.add_argument(
        "--g2-proof",
        default=DEFAULT_G2_PROOF,
    )
    parser.add_argument(
        "--output",
        default=DEFAULT_OUTPUT,
    )
    args = parser.parse_args(argv)

    gateway_attestation = (
        verify_installed_gateway_readonly_attestation(
            REPOSITORY_ROOT
        )
    )

    result = evaluate_g6_runtime_prerequisite(
        read_trusted_runtime_evidence_json(
            args.g5_validation
        ),
        read_trusted_runtime_evidence_json(
            args.completion_status
        ),
        read_trusted_runtime_evidence_json(
            args.g4_shadow
        ),
        read_trusted_runtime_evidence_json(
            args.authorization
        ),
        read_trusted_runtime_evidence_json(
            args.g2_proof
        ),
        gateway_attestation,
    )

    try:
        write_runtime_evidence_atomic(
            args.output,
            result,
        )
    except (
        OSError,
        RuntimeError,
        ValueError,
    ):
        print(
            json.dumps(
                _blocked(
                    "G6_RUNTIME_PREREQUISITE_WRITE_FAILED"
                ),
                indent=2,
                sort_keys=True,
            )
        )
        return 2

    print(
        json.dumps(
            result,
            indent=2,
            sort_keys=True,
        )
    )

    return (
        0
        if result.get("status")
        == "READY_FOR_PAPER_CONNECTOR_SOURCE_REVIEW"
        else 2
    )


if __name__ == "__main__":
    raise SystemExit(main())
