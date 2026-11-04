#!/usr/bin/env python3
"""Validate one strict post-attestation G2 Paper Read-Only proof."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from uuid import UUID

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from scripts.aurora_readiness_summary import (
    EXPECTED_G2_REQUIRED_CHECKS,
)
from scripts.gateway_review_package import (
    load_installed_g2_diagnostic_proof,
)
from engines.ibkr_paper_readiness_engine import (
    evaluate_ibkr_paper_readiness,
)


ENGINE_VERSION = "AURORA G8.6 Strict G2 Post-Review Status"

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
        "gcp_instance_id": None,
        "g0_runtime_proof_sha256": None,
        "next_action": "STOP_AND_REPAIR_G2_POST_REVIEW_PROOF",
        "human_action_required": True,
        "failure_reasons": [reason],
        "broker_submission_allowed": False,
        "paper_order_submission_allowed": False,
        "live_execution_allowed": False,
        "automatic_promotion_allowed": False,
        "real_money_trading_allowed": False,
    }


def _all_permissions_false(payload):
    return (
        isinstance(payload, dict)
        and all(
            payload.get(name) is False
            for name in _PERMISSION_FLAGS
        )
    )


def evaluate_post_review_g2_status(
    expected_run_id,
    g2_proof,
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
            "G2_PROOF_INVALID",
            expected_run_id,
        )

    if g2_proof.get("probe_stage") != "POST_REVIEW_PROBE":
        return _blocked(
            "G2_POST_REVIEW_PROBE_STAGE_INVALID",
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
            "G2_EVIDENCE_RUN_MISMATCH",
            expected_run_id,
        )

    run_mode = g2_proof.get(
        "run_mode"
    )
    provenance = g2_proof.get(
        "runtime_provenance"
    )
    snapshot = g2_proof.get(
        "snapshot"
    )
    attestation = g2_proof.get(
        "gateway_read_only_attestation"
    )
    readiness = g2_proof.get(
        "readiness"
    )

    if not all(
        isinstance(value, dict)
        for value in (
            run_mode,
            provenance,
            snapshot,
            attestation,
            readiness,
        )
    ):
        return _blocked(
            "G2_PROOF_STRUCTURE_INVALID",
            expected_run_id,
        )

    if (
        run_mode.get("mode") != "READ_ONLY"
        or run_mode.get(
            "live_execution_allowed"
        )
        is not False
        or run_mode.get(
            "paper_order_submission_requested"
        )
        is not False
    ):
        return _blocked(
            "G2_RUN_MODE_UNSAFE",
            expected_run_id,
        )

    identity = provenance.get(
        "runtime_cloud_identity"
    )
    instance_id = (
        str(
            identity.get("instance_id") or ""
        ).strip()
        if isinstance(identity, dict)
        else ""
    )
    g0_digest = _hex_digest(
        provenance.get(
            "g0_runtime_proof_sha256"
        )
    )
    provenance_safe = (
        provenance.get("verified") is True
        and provenance.get(
            "failure_reasons"
        )
        == []
        and _all_permissions_false(
            provenance
        )
        and isinstance(identity, dict)
        and instance_id.isdigit()
        and 6 <= len(instance_id) <= 30
        and instance_id[0] != "0"
        and g0_digest is not None
    )
    if not provenance_safe:
        return _blocked(
            "G2_RUNTIME_PROVENANCE_INVALID",
            expected_run_id,
        )

    config = snapshot.get(
        "config"
    )
    if not isinstance(config, dict):
        return _blocked(
            "G2_CONNECTOR_CONFIG_INVALID",
            expected_run_id,
        )

    connector_safe = (
        snapshot.get("status") == "CONNECTED"
        and snapshot.get(
            "connection_status"
        )
        == "CONNECTED"
        and snapshot.get(
            "official_ibapi_available"
        )
        is True
        and config.get("enabled") is True
        and config.get("mode") == "PAPER"
        and config.get("mode_valid") is True
        and config.get("host") == "127.0.0.1"
        and config.get("port") == 4002
        and config.get("port_valid") is True
        and config.get("endpoint_safe") is True
        and config.get("read_only") is True
        and type(
            config.get("client_id")
        )
        is int
        and config.get("client_id") > 0
        and config.get("client_id_valid") is True
        and snapshot.get(
            "order_submission_hard_blocked"
        )
        is True
        and snapshot.get(
            "broker_mutation_surface_hard_blocked"
        )
        is True
        and snapshot.get(
            "client_zero_binding_hard_blocked"
        )
        is True
        and snapshot.get(
            "open_order_observation_mode"
        )
        ==
        "REQ_ALL_OPEN_ORDERS_NON_BINDING"
        and snapshot.get(
            "live_trading_allowed"
        )
        is False
        and snapshot.get(
            "gateway_read_only_configuration_independently_attested"
        )
        is True
    )
    if not connector_safe:
        return _blocked(
            "G2_CONNECTOR_SAFETY_INVALID",
            expected_run_id,
        )

    attestation_safe = (
        attestation.get("status") == "VERIFIED"
        and attestation.get("verified") is True
        and attestation.get(
            "gateway_read_only_configuration_independently_attested"
        )
        is True
        and attestation.get(
            "failure_reasons"
        )
        == []
        and _all_permissions_false(
            attestation
        )
    )
    if not attestation_safe:
        return _blocked(
            "GATEWAY_READ_ONLY_ATTESTATION_NOT_VERIFIED",
            expected_run_id,
        )

    recomputed = evaluate_ibkr_paper_readiness(
        snapshot,
        [],
    )
    recomputed_checks = recomputed.get(
        "checks"
    )
    recomputed_required_names = (
        {
            item["check"]
            for item in recomputed_checks
            if (
                isinstance(item, dict)
                and item.get("required") is True
            )
        }
        if isinstance(
            recomputed_checks,
            list,
        )
        else set()
    )
    recomputed_safe = (
        recomputed.get("readiness")
        == "READY_FOR_PAPER_READ_ONLY"
        and recomputed.get(
            "required_failure_count"
        )
        == 0
        and recomputed.get(
            "diagnostic_read_only_ready"
        )
        is True
        and recomputed.get(
            "gateway_read_only_configuration_independently_attested"
        )
        is True
        and recomputed.get(
            "paper_order_submission_allowed"
        )
        is False
        and recomputed.get(
            "live_execution_allowed"
        )
        is False
        and recomputed_required_names
        ==
        EXPECTED_G2_REQUIRED_CHECKS
        and all(
            item.get("passed") is True
            for item in recomputed_checks
            if item.get("required") is True
        )
    )
    if not recomputed_safe:
        return _blocked(
            "G2_RECOMPUTED_READINESS_NOT_CLEAN",
            expected_run_id,
        )

    checks = readiness.get(
        "checks"
    )
    checks_valid = (
        isinstance(checks, list)
        and bool(checks)
        and all(
            isinstance(item, dict)
            and isinstance(
                item.get("check"),
                str,
            )
            and item.get("check")
            and type(
                item.get("required")
            )
            is bool
            and type(
                item.get("passed")
            )
            is bool
            for item in checks
        )
    )
    if not checks_valid:
        return _blocked(
            "G2_READINESS_CHECKS_INVALID",
            expected_run_id,
        )

    required_names = {
        item["check"]
        for item in checks
        if item["required"] is True
    }
    required_pass = (
        len(
            [
                item
                for item in checks
                if item["required"] is True
                and item["passed"] is not True
            ]
        )
        ==
        0
        and len(
            {
                item["check"]
                for item in checks
            }
        )
        ==
        len(checks)
        and required_names
        ==
        EXPECTED_G2_REQUIRED_CHECKS
    )
    if not required_pass:
        return _blocked(
            "G2_REQUIRED_CHECKS_NOT_CLEAN",
            expected_run_id,
        )

    readiness_safe = (
        readiness.get("readiness")
        == recomputed.get("readiness")
        == "READY_FOR_PAPER_READ_ONLY"
        and readiness.get(
            "required_failure_count"
        )
        == recomputed.get(
            "required_failure_count"
        )
        == 0
        and readiness.get(
            "diagnostic_read_only_ready"
        )
        is True
        and readiness.get(
            "gateway_read_only_configuration_independently_attested"
        )
        is True
        and readiness.get(
            "paper_order_submission_allowed"
        )
        is False
        and readiness.get(
            "live_execution_allowed"
        )
        is False
    )
    if not readiness_safe:
        return _blocked(
            "G2_READINESS_STATE_INVALID",
            expected_run_id,
        )

    return {
        "engine": ENGINE_VERSION,
        "status": "READY_FOR_G3_MARKET_DATA_PROBE",
        "evidence_run_id": expected_run_id,
        "gcp_instance_id": instance_id,
        "g0_runtime_proof_sha256": g0_digest,
        "next_action": "RUN_G3_VERIFIED_REALTIME_MARKET_DATA_PROBE",
        "human_action_required": False,
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

    result = evaluate_post_review_g2_status(
        args.expected_run_id,
        load_installed_g2_diagnostic_proof(),
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
        == "READY_FOR_G3_MARKET_DATA_PROBE"
        else 2
    )


if __name__ == "__main__":
    raise SystemExit(main())
