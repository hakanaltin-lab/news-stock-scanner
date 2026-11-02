#!/usr/bin/env python3
"""Report the fail-closed Gateway independent-review workflow stage.

This command is diagnostic only. It does not write policy, attestation, or
runtime evidence, does not sign anything, and never enables broker execution.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from scripts.gce_identity_bootstrap import build_bootstrap_identity
from engines.gateway_attestation_handoff import (
    build_installed_reviewer_handoff,
)
from scripts.gateway_review_package import (
    build_unsigned_review_package,
)
from engines.gateway_readonly_attestation_verifier import (
    verify_installed_gateway_readonly_attestation,
)


ENGINE_VERSION = "AURORA G7.12 Gateway Review Workflow Status"

_PERMISSION_FLAGS = (
    "broker_submission_allowed",
    "paper_order_submission_allowed",
    "live_execution_allowed",
    "automatic_promotion_allowed",
    "real_money_trading_allowed",
)


def _all_permissions_false(payload):
    return (
        isinstance(payload, dict)
        and all(
            payload.get(name) is False
            for name in _PERMISSION_FLAGS
            if name in payload
        )
        and not any(
            payload.get(name) is True
            for name in _PERMISSION_FLAGS
        )
    )


def _result(
    *,
    status,
    workflow_stage,
    next_action,
    human_action_required,
    runtime_identity_verified,
    handoff_ready,
    review_package_ready,
    signed_attestation_verified,
    failure_reason=None,
):
    return {
        "engine": ENGINE_VERSION,
        "status": status,
        "workflow_stage": workflow_stage,
        "next_action": next_action,
        "human_action_required": human_action_required,
        "runtime_identity_verified": runtime_identity_verified,
        "handoff_ready": handoff_ready,
        "review_package_ready": review_package_ready,
        "signed_attestation_verified": signed_attestation_verified,
        "failure_reasons": (
            [failure_reason]
            if failure_reason
            else []
        ),
        "broker_submission_allowed": False,
        "paper_order_submission_allowed": False,
        "live_execution_allowed": False,
        "automatic_promotion_allowed": False,
        "real_money_trading_allowed": False,
    }


def evaluate_gateway_review_workflow(
    identity_result,
    handoff_result,
    review_package_result,
    attestation_result,
):
    """Map already-sanitized component results to one safe next action."""

    payloads = (
        identity_result,
        handoff_result,
        review_package_result,
    )
    if not all(
        isinstance(payload, dict)
        for payload in (
            identity_result,
            handoff_result,
            review_package_result,
            attestation_result,
        )
    ):
        return _result(
            status="BLOCKED",
            workflow_stage="SAFETY_INVARIANT",
            next_action="STOP_AND_REPAIR_PERMISSION_INVARIANT",
            human_action_required=True,
            runtime_identity_verified=False,
            handoff_ready=False,
            review_package_ready=False,
            signed_attestation_verified=False,
            failure_reason="WORKFLOW_INPUT_INVALID",
        )

    if not all(
        _all_permissions_false(payload)
        for payload in payloads
    ):
        return _result(
            status="BLOCKED",
            workflow_stage="SAFETY_INVARIANT",
            next_action="STOP_AND_REPAIR_PERMISSION_INVARIANT",
            human_action_required=True,
            runtime_identity_verified=False,
            handoff_ready=False,
            review_package_ready=False,
            signed_attestation_verified=False,
            failure_reason="EXECUTION_PERMISSION_INVARIANT_FAILED",
        )

    runtime_identity_verified = (
        identity_result.get("status") == "VERIFIED"
        and identity_result.get("verified") is True
    )
    if not runtime_identity_verified:
        return _result(
            status="BLOCKED",
            workflow_stage="RUNTIME_IDENTITY",
            next_action="FIX_APPROVED_GCE_RUNTIME_IDENTITY",
            human_action_required=True,
            runtime_identity_verified=False,
            handoff_ready=False,
            review_package_ready=False,
            signed_attestation_verified=False,
            failure_reason="RUNTIME_IDENTITY_NOT_VERIFIED",
        )

    handoff_ready = (
        handoff_result.get("status") == "READY_FOR_INDEPENDENT_REVIEW"
        and handoff_result.get("ready_for_independent_review") is True
        and handoff_result.get("attestation_verified") is False
        and handoff_result.get(
            "gateway_read_only_configuration_independently_attested"
        ) is False
    )
    if not handoff_ready:
        return _result(
            status="BLOCKED",
            workflow_stage="TRUST_AND_HANDOFF",
            next_action=(
                "INSTALL_OR_REPAIR_ROOT_POLICY_PUBLIC_KEY_AND_G0_PROOF"
            ),
            human_action_required=True,
            runtime_identity_verified=True,
            handoff_ready=False,
            review_package_ready=False,
            signed_attestation_verified=False,
            failure_reason="HANDOFF_NOT_READY",
        )

    review_package_ready = (
        review_package_result.get("status")
        == "READY_FOR_INDEPENDENT_REVIEW_PACKAGE"
        and review_package_result.get("ready_for_independent_review") is True
        and review_package_result.get("attestation_verified") is False
        and review_package_result.get(
            "gateway_read_only_configuration_independently_attested"
        ) is False
    )
    if not review_package_ready:
        return _result(
            status="BLOCKED",
            workflow_stage="REVIEW_PACKAGE",
            next_action="REPAIR_UNSIGNED_REVIEW_PACKAGE",
            human_action_required=True,
            runtime_identity_verified=True,
            handoff_ready=True,
            review_package_ready=False,
            signed_attestation_verified=False,
            failure_reason="REVIEW_PACKAGE_NOT_READY",
        )

    signed_attestation_verified = (
        attestation_result.get("status") == "VERIFIED"
        and attestation_result.get("verified") is True
        and attestation_result.get(
            "gateway_read_only_configuration_independently_attested"
        ) is True
    )
    if not signed_attestation_verified:
        return _result(
            status="WAITING_FOR_INDEPENDENT_REVIEW",
            workflow_stage="INDEPENDENT_REVIEW",
            next_action=(
                "COMPLETE_INDEPENDENT_REVIEW_AND_INSTALL_SIGNED_ATTESTATION"
            ),
            human_action_required=True,
            runtime_identity_verified=True,
            handoff_ready=True,
            review_package_ready=True,
            signed_attestation_verified=False,
        )

    return _result(
        status="VERIFIED_FOR_G2_READ_ONLY_PROBE",
        workflow_stage="SIGNED_ATTESTATION_VERIFIED",
        next_action="RUN_G2_PAPER_READ_ONLY_PROBE",
        human_action_required=False,
        runtime_identity_verified=True,
        handoff_ready=True,
        review_package_ready=True,
        signed_attestation_verified=True,
    )


def build_installed_gateway_review_workflow_status():
    identity = build_bootstrap_identity()
    handoff = build_installed_reviewer_handoff(
        REPOSITORY_ROOT
    )
    review_package = build_unsigned_review_package(
        handoff
    )
    attestation = verify_installed_gateway_readonly_attestation(
        REPOSITORY_ROOT
    )

    return evaluate_gateway_review_workflow(
        identity,
        handoff,
        review_package,
        attestation,
    )


def main():
    result = build_installed_gateway_review_workflow_status()
    print(json.dumps(result, sort_keys=True))
    return (
        0
        if result["status"]
        in {
            "WAITING_FOR_INDEPENDENT_REVIEW",
            "VERIFIED_FOR_G2_READ_ONLY_PROBE",
        }
        else 2
    )


if __name__ == "__main__":
    raise SystemExit(main())
