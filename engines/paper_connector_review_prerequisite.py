"""G8.12 broker-independent G6 runtime prerequisite review gate.

This gate binds the trusted G5 human authorization to the same real IBKR Paper
Read-Only evidence and independently verified Gateway/TWS Read-Only
attestation. It is review-only: it cannot connect to a broker, construct a
broker order, materialize a broker request, or authorize submission.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import hmac
import json
from uuid import UUID

from engines.gce_runtime_identity import (
    EXPECTED_INSTANCE_NAME,
    EXPECTED_PROJECT_ID,
    EXPECTED_ZONE,
)
from engines.ibkr_paper_readiness_engine import (
    evaluate_ibkr_paper_readiness,
)
from engines.paper_order_authorization_gate import (
    AUTH_VERSION,
    evaluate_manual_paper_authorization,
)


ENGINE_VERSION = (
    "AURORA G8.12 G6 Paper Connector Runtime Prerequisite"
)
DEFAULT_MAX_G2_AGE_SECONDS = 300

G5_REQUIRED_CHECKS = {
    "authorization_field_set_exact",
    "completion_validated_shadow_only",
    "completion_check_set_exact_and_passed",
    "completion_runtime_binding_valid",
    "shadow_order_accepted",
    "authorization_version",
    "explicit_human_approval",
    "paper_mode_only",
    "single_order_scope",
    "authorization_id_uuid4",
    "authorization_current",
    "completion_digest_bound",
    "shadow_order_digest_bound",
    "completion_shadow_order_digest_bound",
    "authorization_permissions_non_executable",
}

EXPECTED_G6_RUNTIME_CHECKS = {
    "g5_validation_safe",
    "g5_recomputed_from_trusted_sources",
    "g5_authorization_artifact_digest_valid",
    "g5_completion_digest_bound",
    "g5_shadow_digest_bound",
    "g2_proof_digest_bound",
    "g2_evidence_run_bound",
    "g2_post_review_probe_stage",
    "g2_run_mode_read_only",
    "g2_connector_config_exact",
    "g2_runtime_provenance_bound",
    "g2_fresh",
    "g2_readiness_recomputed",
    "g2_recorded_readiness_consistent",
    "g2_recorded_required_checks_match_recomputed",
    "paper_account_fingerprint_verified",
    "gateway_attestation_runtime_verified",
    "gateway_attestation_exactly_bound",
    "gateway_attestation_runtime_identity_bound",
    "git_sha_bound_to_attestation",
}

_PERMISSION_FLAGS = (
    "broker_submission_allowed",
    "paper_order_submission_allowed",
    "live_execution_allowed",
    "automatic_promotion_allowed",
    "real_money_trading_allowed",
)

_REVIEW_DISABLED_FLAGS = (
    "implementation_allowed",
    "connection_allowed",
    "broker_request_materialization_allowed",
    "broker_order_object_allowed",
    "automatic_retry_allowed",
    "automatic_cancel_allowed",
    "automatic_modify_allowed",
)


def _digest(payload):
    encoded = json.dumps(
        payload or {},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _uuid4(value):
    text = str(value or "").strip()
    try:
        parsed = UUID(text)
    except (ValueError, AttributeError):
        return None
    if parsed.version != 4 or str(parsed) != text:
        return None
    return text


def _sha256(value):
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


def _git_sha(value):
    text = str(value or "").strip().lower()
    if (
        len(text) != 40
        or any(
            character not in "0123456789abcdef"
            for character in text
        )
    ):
        return None
    return text


def _utc_datetime(value):
    if isinstance(value, datetime):
        parsed = value
    else:
        text = str(value or "").strip()
        if not text:
            return None
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def _safe_flags(payload):
    return (
        isinstance(payload, dict)
        and all(
            name in payload
            and payload.get(name) is False
            for name in _PERMISSION_FLAGS
        )
    )


def _blocked(reason, checks=None):
    return {
        "engine": ENGINE_VERSION,
        "status": "BLOCKED",
        "reason": reason,
        "checks": checks or {},
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


def _verified_fingerprints(snapshot):
    guard = (
        snapshot.get("paper_account_guard")
        if isinstance(
            snapshot.get("paper_account_guard"),
            dict,
        )
        else {}
    )
    values = guard.get(
        "verified_account_fingerprints"
    )
    if not isinstance(values, list) or len(values) != 1:
        return ()

    value = values[0]
    if (
        not isinstance(value, str)
        or len(value) != 15
        or not value.startswith("IBKR-")
        or any(
            character not in "0123456789ABCDEF"
            for character in value[5:]
        )
    ):
        return ()

    return (value,)


def evaluate_g6_runtime_prerequisite(
    g5_validation,
    completion_status,
    g4_shadow,
    authorization,
    g2_proof,
    gateway_attestation_verification,
    now=None,
    max_g2_age_seconds=DEFAULT_MAX_G2_AGE_SECONDS,
):
    now = _utc_datetime(now) or datetime.now(timezone.utc)

    payloads = (
        g5_validation,
        completion_status,
        g4_shadow,
        authorization,
        g2_proof,
        gateway_attestation_verification,
    )
    if not all(
        isinstance(item, dict)
        for item in payloads
    ):
        return _blocked(
            "G6_RUNTIME_PREREQUISITE_INPUT_INVALID"
        )

    if (
        type(max_g2_age_seconds) is not int
        or not 60 <= max_g2_age_seconds <= 900
    ):
        return _blocked(
            "G2_MAX_AGE_INVALID"
        )

    shadow_order = (
        g4_shadow.get("shadow_order")
        if isinstance(
            g4_shadow.get("shadow_order"),
            dict,
        )
        else {}
    )

    recomputed_g5 = evaluate_manual_paper_authorization(
        completion_status,
        shadow_order,
        authorization,
        now=now,
    )

    g5_checks = (
        g5_validation.get("checks")
        if isinstance(
            g5_validation.get("checks"),
            dict,
        )
        else {}
    )
    g5_checks_valid = (
        set(g5_checks) == G5_REQUIRED_CHECKS
        and all(
            g5_checks.get(name) is True
            for name in G5_REQUIRED_CHECKS
        )
    )

    recomputed_checks = (
        recomputed_g5.get("checks")
        if isinstance(
            recomputed_g5.get("checks"),
            dict,
        )
        else {}
    )
    recomputed_g5_valid = (
        recomputed_g5.get("status")
        == "MANUAL_PAPER_AUTHORIZATION_VALIDATED"
        and set(recomputed_checks) == G5_REQUIRED_CHECKS
        and all(
            recomputed_checks.get(name) is True
            for name in G5_REQUIRED_CHECKS
        )
        and _safe_flags(recomputed_g5)
    )

    invariant_fields = (
        "authorization_id",
        "authorization_version",
        "authorization_artifact_sha256",
        "completion_status_sha256",
        "shadow_order_sha256",
        "evidence_run_id",
        "gce_instance_id",
        "g0_g1_proof_sha256",
        "g2_paper_read_only_proof_sha256",
        "gateway_read_only_attestation_sha256",
        "readiness_proof_sha256",
        "g4_ledger_receipt_sha256",
        "scope",
        "mode",
        "authorization_issued_at",
        "authorization_expires_at",
        "next_gate",
    )
    g5_recomputed_bound = (
        recomputed_g5_valid
        and all(
            g5_validation.get(name)
            == recomputed_g5.get(name)
            for name in invariant_fields
        )
    )

    g5_safe = (
        g5_validation.get("status")
        == "MANUAL_PAPER_AUTHORIZATION_VALIDATED"
        and g5_validation.get("next_gate")
        == "PAPER_EXECUTION_CONNECTOR_REVIEW_REQUIRED"
        and g5_validation.get(
            "authorization_version"
        )
        == AUTH_VERSION
        and g5_validation.get(
            "authorization_can_be_consumed_once"
        )
        is True
        and g5_validation.get(
            "authorization_is_pre_execution_only"
        )
        is True
        and g5_checks_valid
        and _safe_flags(g5_validation)
    )

    g5_run_id = _uuid4(
        g5_validation.get("evidence_run_id")
    )
    g5_instance_id = str(
        g5_validation.get("gce_instance_id")
        or
        ""
    ).strip()
    g5_g0_digest = _sha256(
        g5_validation.get("g0_g1_proof_sha256")
    )
    g5_g2_digest = _sha256(
        g5_validation.get(
            "g2_paper_read_only_proof_sha256"
        )
    )
    g5_attestation_digest = _sha256(
        g5_validation.get(
            "gateway_read_only_attestation_sha256"
        )
    )

    g2_run_id = _uuid4(
        g2_proof.get("evidence_run_id")
    )
    g2_git_sha = _git_sha(
        g2_proof.get("git_sha")
    )
    g2_run_mode = (
        g2_proof.get("run_mode")
        if isinstance(
            g2_proof.get("run_mode"),
            dict,
        )
        else {}
    )
    g2_snapshot = (
        g2_proof.get("snapshot")
        if isinstance(
            g2_proof.get("snapshot"),
            dict,
        )
        else {}
    )
    g2_readiness_recorded = (
        g2_proof.get("readiness")
        if isinstance(
            g2_proof.get("readiness"),
            dict,
        )
        else {}
    )
    g2_provenance = (
        g2_proof.get("runtime_provenance")
        if isinstance(
            g2_proof.get("runtime_provenance"),
            dict,
        )
        else {}
    )
    g2_identity = (
        g2_provenance.get(
            "runtime_cloud_identity"
        )
        if isinstance(
            g2_provenance.get(
                "runtime_cloud_identity"
            ),
            dict,
        )
        else {}
    )
    g2_attestation = (
        g2_proof.get(
            "gateway_read_only_attestation"
        )
        if isinstance(
            g2_proof.get(
                "gateway_read_only_attestation"
            ),
            dict,
        )
        else {}
    )

    g2_recomputed = evaluate_ibkr_paper_readiness(
        g2_snapshot,
        [],
    )

    g2_config = (
        g2_snapshot.get("config")
        if isinstance(
            g2_snapshot.get("config"),
            dict,
        )
        else {}
    )

    snapshot_timestamp = _utc_datetime(
        g2_snapshot.get("timestamp")
    )
    snapshot_completed_at = _utc_datetime(
        g2_snapshot.get("snapshot_completed_at_utc")
    )
    readiness_timestamp = _utc_datetime(
        g2_readiness_recorded.get("timestamp")
    )
    snapshot_age_seconds = (
        (now - snapshot_timestamp).total_seconds()
        if snapshot_timestamp is not None
        else None
    )
    snapshot_completion_age_seconds = (
        (now - snapshot_completed_at).total_seconds()
        if snapshot_completed_at is not None
        else None
    )
    readiness_age_seconds = (
        (now - readiness_timestamp).total_seconds()
        if readiness_timestamp is not None
        else None
    )
    timestamp_chain_seconds = (
        (readiness_timestamp - snapshot_timestamp).total_seconds()
        if (
            readiness_timestamp is not None
            and snapshot_timestamp is not None
        )
        else None
    )
    snapshot_collection_seconds = (
        (snapshot_completed_at - snapshot_timestamp).total_seconds()
        if (
            snapshot_completed_at is not None
            and snapshot_timestamp is not None
        )
        else None
    )
    completion_to_readiness_seconds = (
        (readiness_timestamp - snapshot_completed_at).total_seconds()
        if (
            readiness_timestamp is not None
            and snapshot_completed_at is not None
        )
        else None
    )

    recomputed_checks = (
        g2_recomputed.get("checks")
        if isinstance(
            g2_recomputed.get("checks"),
            list,
        )
        else []
    )
    recorded_checks = (
        g2_readiness_recorded.get("checks")
        if isinstance(
            g2_readiness_recorded.get("checks"),
            list,
        )
        else []
    )

    def _required_check_map(rows):
        if not rows:
            return None
        result = {}
        for item in rows:
            if (
                not isinstance(item, dict)
                or not isinstance(
                    item.get("check"),
                    str,
                )
                or type(
                    item.get("required")
                )
                is not bool
                or type(
                    item.get("passed")
                )
                is not bool
            ):
                return None
            name = item["check"]
            if name in result:
                return None
            if item["required"]:
                result[name] = item["passed"]
        return result

    recomputed_required_checks = _required_check_map(
        recomputed_checks
    )
    recorded_required_checks = _required_check_map(
        recorded_checks
    )

    fingerprints = _verified_fingerprints(
        g2_snapshot
    )

    runtime_attestation_digest = _digest(
        gateway_attestation_verification
    )
    g2_attestation_digest = _digest(
        g2_attestation
    )

    checks = {
        "g5_validation_safe": g5_safe,
        "g5_recomputed_from_trusted_sources": (
            g5_recomputed_bound
        ),
        "g5_authorization_artifact_digest_valid": (
            _sha256(
                g5_validation.get(
                    "authorization_artifact_sha256"
                )
            )
            is not None
            and hmac.compare_digest(
                g5_validation[
                    "authorization_artifact_sha256"
                ],
                _digest(authorization),
            )
        ),
        "g5_completion_digest_bound": (
            _sha256(
                g5_validation.get(
                    "completion_status_sha256"
                )
            )
            is not None
            and hmac.compare_digest(
                g5_validation[
                    "completion_status_sha256"
                ],
                _digest(completion_status),
            )
        ),
        "g5_shadow_digest_bound": (
            _sha256(
                g5_validation.get(
                    "shadow_order_sha256"
                )
            )
            is not None
            and bool(shadow_order)
            and hmac.compare_digest(
                g5_validation[
                    "shadow_order_sha256"
                ],
                _digest(shadow_order),
            )
        ),
        "g2_proof_digest_bound": (
            g5_g2_digest is not None
            and hmac.compare_digest(
                g5_g2_digest,
                _digest(g2_proof),
            )
        ),
        "g2_evidence_run_bound": (
            g5_run_id is not None
            and g5_run_id == g2_run_id
        ),
        "g2_post_review_probe_stage": (
            g2_proof.get("probe_stage")
            == "POST_REVIEW_PROBE"
        ),
        "g2_run_mode_read_only": (
            g2_run_mode.get("mode") == "READ_ONLY"
            and g2_run_mode.get("mode_valid") is True
            and g2_run_mode.get("read_only") is True
            and g2_run_mode.get("dry_run") is False
            and g2_run_mode.get("safe_off") is False
            and g2_run_mode.get(
                "paper_order_submission_requested"
            )
            is False
            and g2_run_mode.get(
                "live_execution_allowed"
            )
            is False
        ),
        "g2_connector_config_exact": (
            g2_config.get("enabled") is True
            and g2_config.get("mode") == "PAPER"
            and g2_config.get("mode_valid") is True
            and g2_config.get("host") == "127.0.0.1"
            and g2_config.get("port") == 4002
            and g2_config.get("port_valid") is True
            and g2_config.get("endpoint_safe") is True
            and g2_config.get("read_only") is True
            and type(g2_config.get("client_id")) is int
            and g2_config.get("client_id") > 0
            and g2_config.get("client_id_valid") is True
            and g2_config.get("timeout_valid") is True
        ),
        "g2_runtime_provenance_bound": (
            g2_provenance.get("verified") is True
            and g2_provenance.get(
                "failure_reasons"
            )
            == []
            and _safe_flags(g2_provenance)
            and g2_identity.get("project_id")
            == EXPECTED_PROJECT_ID
            and g2_identity.get("instance_name")
            == EXPECTED_INSTANCE_NAME
            and g2_identity.get("zone")
            == EXPECTED_ZONE
            and g5_instance_id.isdigit()
            and g5_instance_id
            == str(
                g2_identity.get("instance_id")
                or ""
            ).strip()
            and g5_g0_digest is not None
            and g5_g0_digest
            == _sha256(
                g2_provenance.get(
                    "g0_runtime_proof_sha256"
                )
            )
        ),
        "g2_fresh": (
            snapshot_age_seconds is not None
            and snapshot_completion_age_seconds is not None
            and readiness_age_seconds is not None
            and timestamp_chain_seconds is not None
            and snapshot_collection_seconds is not None
            and completion_to_readiness_seconds is not None
            and -2 <= snapshot_age_seconds
            <= max_g2_age_seconds
            and -2 <= snapshot_completion_age_seconds
            <= max_g2_age_seconds
            and -2 <= readiness_age_seconds
            <= max_g2_age_seconds
            and 0 <= timestamp_chain_seconds <= 60
            and 0 <= snapshot_collection_seconds <= 60
            and 0 <= completion_to_readiness_seconds <= 60
        ),
        "g2_readiness_recomputed": (
            g2_recomputed.get("readiness")
            == "READY_FOR_PAPER_READ_ONLY"
            and g2_recomputed.get(
                "required_failure_count"
            )
            == 0
            and g2_recomputed.get(
                "paper_order_submission_allowed"
            )
            is False
            and g2_recomputed.get(
                "live_execution_allowed"
            )
            is False
        ),
        "g2_recorded_readiness_consistent": (
            g2_readiness_recorded.get(
                "readiness"
            )
            == "READY_FOR_PAPER_READ_ONLY"
            and g2_readiness_recorded.get(
                "required_failure_count"
            )
            == 0
            and g2_readiness_recorded.get(
                "gateway_read_only_configuration_independently_attested"
            )
            is True
            and g2_readiness_recorded.get(
                "paper_order_submission_allowed"
            )
            is False
            and g2_readiness_recorded.get(
                "live_execution_allowed"
            )
            is False
        ),
        "g2_recorded_required_checks_match_recomputed": (
            isinstance(
                recorded_required_checks,
                dict,
            )
            and isinstance(
                recomputed_required_checks,
                dict,
            )
            and recorded_required_checks
            == recomputed_required_checks
            and bool(recorded_required_checks)
            and all(
                value is True
                for value in recorded_required_checks.values()
            )
        ),
        "paper_account_fingerprint_verified": (
            len(fingerprints) == 1
            and g2_snapshot.get(
                "paper_account_guard",
                {},
            ).get(
                "paper_account_verified"
            )
            is True
        ),
        "gateway_attestation_runtime_verified": (
            gateway_attestation_verification.get(
                "status"
            )
            == "VERIFIED"
            and gateway_attestation_verification.get(
                "verified"
            )
            is True
            and gateway_attestation_verification.get(
                "gateway_read_only_configuration_independently_attested"
            )
            is True
            and gateway_attestation_verification.get(
                "failure_reasons"
            )
            == []
            and _safe_flags(
                gateway_attestation_verification
            )
        ),
        "gateway_attestation_exactly_bound": (
            g5_attestation_digest is not None
            and hmac.compare_digest(
                g5_attestation_digest,
                g2_attestation_digest,
            )
            and hmac.compare_digest(
                g5_attestation_digest,
                runtime_attestation_digest,
            )
        ),
        "gateway_attestation_runtime_identity_bound": (
            g5_instance_id.isdigit()
            and gateway_attestation_verification.get(
                "gcp_project_id"
            )
            == EXPECTED_PROJECT_ID
            and gateway_attestation_verification.get(
                "gcp_instance_id"
            )
            == g5_instance_id
            and gateway_attestation_verification.get(
                "g0_runtime_proof_sha256"
            )
            == g5_g0_digest
            and g2_attestation.get(
                "gcp_project_id"
            )
            == EXPECTED_PROJECT_ID
            and g2_attestation.get(
                "gcp_instance_id"
            )
            == g5_instance_id
            and g2_attestation.get(
                "g0_runtime_proof_sha256"
            )
            == g5_g0_digest
        ),
        "git_sha_bound_to_attestation": (
            g2_git_sha is not None
            and gateway_attestation_verification.get(
                "git_sha"
            )
            == g2_git_sha
            and g2_attestation.get(
                "git_sha"
            )
            == g2_git_sha
        ),
    }

    if set(checks) != EXPECTED_G6_RUNTIME_CHECKS:
        return _blocked(
            "G6_RUNTIME_CHECK_SET_DRIFT",
            checks,
        )

    failures = [
        name
        for name, passed in checks.items()
        if not passed
    ]

    if failures:
        return _blocked(
            "G6_RUNTIME_PREREQUISITES_NOT_SATISFIED",
            checks,
        )

    return {
        "engine": ENGINE_VERSION,
        "generated_at": now.isoformat(),
        "status": "READY_FOR_PAPER_CONNECTOR_SOURCE_REVIEW",
        "checks": checks,
        "g5_validation_sha256": _digest(
            g5_validation
        ),
        "authorization_id": g5_validation.get(
            "authorization_id"
        ),
        "authorization_artifact_sha256": (
            g5_validation.get(
                "authorization_artifact_sha256"
            )
        ),
        "evidence_run_id": g5_run_id,
        "g2_probe_stage": (
            g2_proof.get("probe_stage")
            if checks["g2_post_review_probe_stage"]
            else None
        ),
        "git_sha": g2_git_sha,
        "gce_instance_id": g5_instance_id,
        "g0_g1_proof_sha256": g5_g0_digest,
        "g2_paper_read_only_proof_sha256": (
            g5_g2_digest
        ),
        "gateway_read_only_attestation_sha256": (
            g5_attestation_digest
        ),
        "paper_account_fingerprints": list(
            fingerprints
        ),
        "g2_evidence_age_seconds": round(
            max(
                0.0,
                readiness_age_seconds,
            ),
            3,
        ),
        "g2_snapshot_age_seconds": round(
            max(
                0.0,
                snapshot_age_seconds,
            ),
            3,
        ),
        "g2_snapshot_completion_age_seconds": round(
            max(
                0.0,
                snapshot_completion_age_seconds,
            ),
            3,
        ),
        "independent_source_review_required": True,
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
        "next_gate": (
            "REBASE_AND_REVIEW_BROKER_ADAPTER_SOURCE_AGAINST_G8_12"
        ),
    }
