#!/usr/bin/env python3
"""Validate one trusted human G5 Paper authorization artifact.

This CLI is pre-execution only. It reads the trusted G0-G4 completion artifact,
the trusted G4 shadow artifact, and one trusted human-created authorization
artifact. It never imports a broker API and never authorizes submission.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from engines.paper_order_authorization_gate import (
    evaluate_manual_paper_authorization,
)
from scripts.gateway_review_package import (
    read_trusted_runtime_evidence_json,
)
from scripts.ibkr_paper_probe import (
    write_runtime_evidence_atomic,
)


DEFAULT_COMPLETION_STATUS = (
    "runtime/aurora_project_status/latest.json"
)
DEFAULT_G4_SHADOW = (
    "runtime/aurora_g4_shadow/latest.json"
)
DEFAULT_OUTPUT = (
    "runtime/aurora_g5_authorization/latest.json"
)

_PERMISSION_FLAGS = (
    "broker_submission_allowed",
    "paper_order_submission_allowed",
    "live_execution_allowed",
    "automatic_promotion_allowed",
    "real_money_trading_allowed",
)


def _blocked(reason):
    return {
        "engine": "AURORA G8.10 Trusted G5 Authorization CLI",
        "status": "BLOCKED",
        "reason": reason,
        "broker_submission_allowed": False,
        "paper_order_submission_allowed": False,
        "live_execution_allowed": False,
        "automatic_promotion_allowed": False,
        "real_money_trading_allowed": False,
        "next_gate": "REPAIR_TRUSTED_G5_AUTHORIZATION_EVIDENCE",
    }


def _safe_flags(payload):
    return (
        isinstance(payload, dict)
        and all(
            name in payload
            and payload.get(name) is False
            for name in _PERMISSION_FLAGS
        )
    )


def evaluate_trusted_g5_preflight(
    completion_status,
    g4_shadow,
    authorization,
    now=None,
):
    if not isinstance(completion_status, dict):
        return _blocked(
            "COMPLETION_STATUS_INVALID"
        )

    if not isinstance(g4_shadow, dict):
        return _blocked(
            "G4_SHADOW_PROOF_INVALID"
        )

    if not isinstance(authorization, dict):
        return _blocked(
            "AUTHORIZATION_ARTIFACT_INVALID"
        )

    shadow_order = g4_shadow.get(
        "shadow_order"
    )
    if (
        g4_shadow.get("status") != "SHADOW_ACCEPTED"
        or not _safe_flags(g4_shadow)
        or not isinstance(
            shadow_order,
            dict,
        )
        or not _safe_flags(
            shadow_order
        )
    ):
        return _blocked(
            "G4_SHADOW_PROOF_NOT_SAFE"
        )

    result = evaluate_manual_paper_authorization(
        completion_status,
        shadow_order,
        authorization,
        now=now,
    )

    if not isinstance(result, dict):
        return _blocked(
            "G5_AUTHORIZATION_RESULT_INVALID"
        )

    if not _safe_flags(result):
        return _blocked(
            "G5_AUTHORIZATION_PERMISSION_INVARIANT_FAILED"
        )

    return result


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--authorization",
        required=True,
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
        "--output",
        default=DEFAULT_OUTPUT,
    )
    args = parser.parse_args(argv)

    result = evaluate_trusted_g5_preflight(
        read_trusted_runtime_evidence_json(
            args.completion_status
        ),
        read_trusted_runtime_evidence_json(
            args.g4_shadow
        ),
        read_trusted_runtime_evidence_json(
            args.authorization
        ),
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
                    "G5_RUNTIME_EVIDENCE_WRITE_FAILED"
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
        == "MANUAL_PAPER_AUTHORIZATION_VALIDATED"
        else 2
    )


if __name__ == "__main__":
    raise SystemExit(main())
