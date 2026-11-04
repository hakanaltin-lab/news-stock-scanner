#!/usr/bin/env python3
"""Sanitized G6 operator acceptance status.

This command never connects to IBKR, writes broker evidence, signs an
attestation, or enables any execution permission. It only tells the operator
which safe acceptance step is next.
"""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.gce_identity_bootstrap import build_bootstrap_identity
from scripts.gateway_review_workflow_status import (
    build_installed_gateway_review_workflow_status,
)

_PERMISSION_FLAGS = (
    "broker_submission_allowed",
    "paper_order_submission_allowed",
    "live_execution_allowed",
    "automatic_promotion_allowed",
    "real_money_trading_allowed",
)


def build_g6_operator_acceptance_status(identity=None, review=None):
    identity = build_bootstrap_identity() if identity is None else identity
    review = (
        build_installed_gateway_review_workflow_status()
        if review is None else review
    )

    identity_ok = (
        isinstance(identity, dict)
        and identity.get("status") == "VERIFIED"
        and identity.get("verified") is True
        and identity.get("failure_reasons") == []
        and all(identity.get(flag) is False for flag in _PERMISSION_FLAGS)
    )
    review_safe = (
        isinstance(review, dict)
        and all(review.get(flag) is False for flag in _PERMISSION_FLAGS)
    )

    next_action = "STOP_AND_REPAIR_GCE_IDENTITY"
    stage = "RUNTIME_IDENTITY"
    ready_for_broker_read = False

    if identity_ok and review_safe:
        status = review.get("status")
        workflow_stage = review.get("workflow_stage")
        action = review.get("next_action")

        if (
            status == "BLOCKED"
            and workflow_stage == "REVIEW_PACKAGE"
            and action == "RUN_FRESH_G2_DIAGNOSTIC_PRE_REVIEW"
        ):
            stage = "PRE_REVIEW_DIAGNOSTIC"
            next_action = "RUN_FRESH_G2_DIAGNOSTIC_PRE_REVIEW"
            ready_for_broker_read = True
        elif (
            status == "WAITING_FOR_INDEPENDENT_REVIEW"
            and workflow_stage == "INDEPENDENT_REVIEW"
        ):
            stage = "INDEPENDENT_REVIEW"
            next_action = "COMPLETE_INDEPENDENT_REVIEW_AND_INSTALL_SIGNED_ATTESTATION"
        elif (
            status == "VERIFIED_FOR_G2_READ_ONLY_PROBE"
            and workflow_stage == "SIGNED_ATTESTATION_VERIFIED"
            and action == "RUN_G2_PAPER_READ_ONLY_PROBE"
        ):
            stage = "POST_REVIEW_PROBE"
            next_action = "RUN_G2_PAPER_READ_ONLY_PROBE"
            ready_for_broker_read = True
        else:
            stage = "ACCEPTANCE_BLOCKED"
            next_action = action or "STOP_AND_REPAIR_REVIEW_WORKFLOW"

    result_status = (
        "READY_FOR_SAFE_BROKER_READ"
        if ready_for_broker_read
        else (
            "WAITING_FOR_HUMAN_REVIEW"
            if stage == "INDEPENDENT_REVIEW"
            else "BLOCKED"
        )
    )

    return {
        "engine": "AURORA G6 Operator Acceptance Status",
        "status": result_status,
        "stage": stage,
        "next_action": next_action,
        "runtime_identity_verified": identity_ok,
        "signed_attestation_verified": (
            bool(review.get("signed_attestation_verified"))
            if isinstance(review, dict) else False
        ),
        "ready_for_broker_read": ready_for_broker_read,
        "broker_submission_allowed": False,
        "paper_order_submission_allowed": False,
        "live_execution_allowed": False,
        "automatic_promotion_allowed": False,
        "real_money_trading_allowed": False,
    }


def main():
    try:
        result = build_g6_operator_acceptance_status()
    except (OSError, RuntimeError, ValueError, TypeError, KeyError):
        result = {
            "engine": "AURORA G6 Operator Acceptance Status",
            "status": "BLOCKED",
            "stage": "STATUS_EVALUATION",
            "next_action": "STOP_AND_REPAIR_ACCEPTANCE_STATUS",
            "runtime_identity_verified": False,
            "signed_attestation_verified": False,
            "ready_for_broker_read": False,
            "broker_submission_allowed": False,
            "paper_order_submission_allowed": False,
            "live_execution_allowed": False,
            "automatic_promotion_allowed": False,
            "real_money_trading_allowed": False,
        }

    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "READY_FOR_SAFE_BROKER_READ" else 2


if __name__ == "__main__":
    raise SystemExit(main())
