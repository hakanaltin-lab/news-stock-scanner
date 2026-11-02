#!/usr/bin/env python3
"""Build a sanitized unsigned Gateway Read-Only review package.

This command never signs evidence and never creates a positive attestation.
It converts a verified G7.10 reviewer handoff into a REVIEW_REQUIRED template
that an independent reviewer must complete and sign off the trading VPS.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from engines.gateway_attestation_handoff import (
    HANDOFF_REQUEST_TYPE,
    build_installed_reviewer_handoff,
)
from engines.gateway_readonly_attestation_verifier import (
    ATTESTATION_TYPE,
    SIGNATURE_ALGORITHM,
)


PACKAGE_TYPE = "IBKR_GATEWAY_READ_ONLY_REVIEW_PACKAGE_V1"

_HANDOFF_REQUEST_FIELDS = {
    "request_schema_version",
    "request_type",
    "requested_control",
    "generated_at_utc",
    "git_sha",
    "instance_name",
    "zone",
    "broker_mode",
    "gateway_port",
    "reviewer_id",
    "reviewer_public_key_sha256",
    "gcp_project_id",
    "gcp_instance_id",
    "reviewer_policy_sha256",
    "g0_runtime_proof_sha256",
    "g0_runtime_proof_generated_at",
    "g0_runtime_project_id",
    "g0_runtime_zone",
    "g0_runtime_vm_name",
    "g0_runtime_instance_id",
    "operator_asserts_gateway_read_only",
    "requires_human_gateway_configuration_review",
    "signed_attestation_required",
    "broker_submission_allowed",
    "paper_order_submission_allowed",
    "live_execution_allowed",
    "automatic_promotion_allowed",
    "real_money_trading_allowed",
}


def _canonical_sha256(payload):
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _blocked(reason):
    return {
        "package_type": PACKAGE_TYPE,
        "package_schema_version": 1,
        "status": "BLOCKED",
        "ready_for_independent_review": False,
        "attestation_verified": False,
        "gateway_read_only_configuration_independently_attested": False,
        "failure_reasons": [reason],
        "handoff_request_sha256": None,
        "handoff_request": None,
        "unsigned_artifact_template": None,
        "broker_submission_allowed": False,
        "paper_order_submission_allowed": False,
        "live_execution_allowed": False,
        "automatic_promotion_allowed": False,
        "real_money_trading_allowed": False,
    }


def build_unsigned_review_package(handoff_result):
    if not isinstance(handoff_result, dict):
        return _blocked("HANDOFF_RESULT_INVALID")

    request = handoff_result.get("handoff_request")
    safe_handoff = (
        handoff_result.get("status") == "READY_FOR_INDEPENDENT_REVIEW"
        and handoff_result.get("ready_for_independent_review") is True
        and handoff_result.get("attestation_verified") is False
        and handoff_result.get(
            "gateway_read_only_configuration_independently_attested"
        ) is False
        and isinstance(request, dict)
        and set(request) == _HANDOFF_REQUEST_FIELDS
        and request.get("request_schema_version") == 3
        and request.get("request_type") == HANDOFF_REQUEST_TYPE
        and request.get("requested_control") == ATTESTATION_TYPE
        and request.get("operator_asserts_gateway_read_only") is False
        and request.get(
            "requires_human_gateway_configuration_review"
        ) is True
        and request.get("signed_attestation_required") is True
        and all(
            handoff_result.get(name) is False
            for name in (
                "broker_submission_allowed",
                "paper_order_submission_allowed",
                "live_execution_allowed",
                "automatic_promotion_allowed",
                "real_money_trading_allowed",
            )
        )
        and all(
            request.get(name) is False
            for name in (
                "broker_submission_allowed",
                "paper_order_submission_allowed",
                "live_execution_allowed",
                "automatic_promotion_allowed",
                "real_money_trading_allowed",
            )
        )
    )
    if not safe_handoff:
        return _blocked("HANDOFF_RESULT_NOT_SAFE_FOR_REVIEW_PACKAGE")

    template = {
        "schema_version": 3,
        "attestation_id": None,
        "attestation_type": ATTESTATION_TYPE,
        "decision": "REVIEW_REQUIRED",
        "reviewer_id": request.get("reviewer_id"),
        "captured_at_utc": None,
        "expires_at_utc": None,
        "git_sha": request.get("git_sha"),
        "instance_name": request.get("instance_name"),
        "zone": request.get("zone"),
        "gcp_project_id": request.get("gcp_project_id"),
        "gcp_instance_id": request.get("gcp_instance_id"),
        "broker_mode": request.get("broker_mode"),
        "gateway_port": request.get("gateway_port"),
        "read_only_api_enabled": None,
        "evidence_sha256": None,
        "g0_runtime_proof_sha256": request.get(
            "g0_runtime_proof_sha256"
        ),
        "signature_algorithm": SIGNATURE_ALGORITHM,
        "signature_b64": None,
    }

    return {
        "package_type": PACKAGE_TYPE,
        "package_schema_version": 1,
        "status": "READY_FOR_INDEPENDENT_REVIEW_PACKAGE",
        "ready_for_independent_review": True,
        "attestation_verified": False,
        "gateway_read_only_configuration_independently_attested": False,
        "failure_reasons": [],
        "handoff_request_sha256": _canonical_sha256(request),
        "handoff_request": request,
        "unsigned_artifact_template": template,
        "reviewer_must_set": [
            "attestation_id",
            "decision=ATTESTED only after independent review",
            "captured_at_utc",
            "expires_at_utc",
            "read_only_api_enabled=true only after independent review",
            "evidence_sha256",
            "signature_b64",
        ],
        "broker_submission_allowed": False,
        "paper_order_submission_allowed": False,
        "live_execution_allowed": False,
        "automatic_promotion_allowed": False,
        "real_money_trading_allowed": False,
    }


def main():
    handoff = build_installed_reviewer_handoff(
        REPOSITORY_ROOT
    )
    result = build_unsigned_review_package(
        handoff
    )
    print(
        json.dumps(
            result,
            sort_keys=True,
        )
    )
    return (
        0
        if result["status"]
        == "READY_FOR_INDEPENDENT_REVIEW_PACKAGE"
        else 2
    )


if __name__ == "__main__":
    raise SystemExit(main())
