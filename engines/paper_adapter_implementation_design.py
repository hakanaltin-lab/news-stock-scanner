"""G8.16 non-executable Paper adapter implementation design gate.

This gate freezes an exact future adapter safety design only after an
independently signed source review has been verified. It does not import IBKR,
connect, materialize a broker request, construct an order, or submit anything.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import math
from uuid import UUID

from engines.paper_adapter_source_attestation import (
    ENGINE_VERSION as SOURCE_ATTESTATION_ENGINE_VERSION,
)
from engines.paper_adapter_source_review import (
    EXPECTED_CLASS,
    SKELETON_VERSION,
)


ENGINE_VERSION = "AURORA G8.16 Paper Adapter Implementation Design"
DESIGN_VERSION = "AURORA_G8_16_ADAPTER_IMPLEMENTATION_DESIGN_V1"

PERMISSION_FLAGS = (
    "implementation_allowed",
    "connection_allowed",
    "broker_request_materialization_allowed",
    "broker_order_object_allowed",
    "automatic_retry_allowed",
    "automatic_cancel_allowed",
    "automatic_modify_allowed",
    "broker_submission_allowed",
    "paper_order_submission_allowed",
    "live_execution_allowed",
    "automatic_promotion_allowed",
    "real_money_trading_allowed",
)

EXPECTED_SOURCE_ATTESTATION_CHECKS = {
    "artifact_is_object",
    "policy_is_object",
    "handoff_is_object",
    "source_review_is_object",
    "artifact_field_set_exact",
    "policy_field_set_exact",
    "handoff_field_set_exact",
    "source_review_field_set_exact",
    "review_request_field_set_exact",
    "artifact_schema_version",
    "artifact_type",
    "decision_attested",
    "review_id_uuid4",
    "signature_algorithm",
    "signature_encoding_valid",
    "ed25519_signature_valid",
    "policy_version",
    "reviewer_id_format",
    "reviewer_matches_policy",
    "policy_skeleton_version",
    "policy_adapter_class",
    "reviewer_public_key_material_valid",
    "policy_public_key_sha256_valid",
    "public_key_matches_policy",
    "policy_max_age_valid",
    "policy_clock_skew_valid",
    "captured_at_valid",
    "expires_at_valid",
    "capture_not_in_future",
    "attestation_not_expired",
    "attestation_age_within_policy",
    "attestation_validity_window_positive",
    "attestation_validity_window_within_policy",
    "reviewer_confirms_source_non_executable",
    "reviewer_confirms_scope_frozen",
    "reviewer_evidence_sha256_valid",
    "handoff_ready_and_non_authorizing",
    "review_request_non_authorizing",
    "review_request_digest_bound",
    "source_review_artifact_digest_bound",
    "source_review_safe_and_non_authorizing",
    "git_sha_bound",
    "repository_clean",
    "source_sha256_bound",
    "signed_source_identity_bound",
    "runtime_provenance_fields_bound",
}

SOURCE_ATTESTATION_FIELDS = {
    "engine",
    "status",
    "verified",
    "adapter_source_independently_attested",
    "reason",
    "checks",
    "review_id",
    "reviewer_id",
    "captured_at_utc",
    "expires_at_utc",
    "git_sha",
    "source_review_artifact_sha256",
    "review_request_sha256",
    "source_sha256",
    "source_policy_sha256",
    "source_attestation_sha256",
    "reviewer_evidence_sha256",
    *PERMISSION_FLAGS,
    "next_gate",
}

DESIGN_FIELDS = {
    "version",
    "broker",
    "api_family",
    "mode",
    "host",
    "port",
    "client_id",
    "asset_type",
    "order_type",
    "time_in_force",
    "whole_share_quantity_only",
    "market_orders_supported",
    "short_selling_supported",
    "fractional_shares_supported",
    "automatic_retry_supported",
    "automatic_cancel_supported",
    "automatic_modify_supported",
    "live_mode_supported",
    "live_port_allowed",
    "credentials_in_repository_allowed",
    "raw_account_id_in_artifacts_allowed",
    "order_submission_implemented",
    "broker_order_object_implemented",
    "broker_request_materialization_implemented",
    "source_attestation_required",
    "one_order_authorization_required",
    "atomic_authorization_reservation_required",
    "idempotency_required",
    "fresh_post_authorization_broker_state_required",
    "stale_price_guard_required",
    "spread_guard_required",
    "available_funds_guard_required",
    "position_no_short_guard_required",
    "append_only_attempt_journal_required",
    "reconciliation_before_retry_required",
    "kill_switch_required",
    "independent_implementation_review_required",
    "explicit_paper_execution_release_required",
    "explicit_live_execution_release_required",
}

EXPECTED_DESIGN_VALUES = {
    "version": DESIGN_VERSION,
    "broker": "IBKR",
    "api_family": "TWS_API",
    "mode": "PAPER",
    "host": "127.0.0.1",
    "port": 4002,
    "client_id": 82,
    "asset_type": "STK",
    "order_type": "LMT",
    "time_in_force": "DAY",
    "whole_share_quantity_only": True,
    "market_orders_supported": False,
    "short_selling_supported": False,
    "fractional_shares_supported": False,
    "automatic_retry_supported": False,
    "automatic_cancel_supported": False,
    "automatic_modify_supported": False,
    "live_mode_supported": False,
    "live_port_allowed": False,
    "credentials_in_repository_allowed": False,
    "raw_account_id_in_artifacts_allowed": False,
    "order_submission_implemented": False,
    "broker_order_object_implemented": False,
    "broker_request_materialization_implemented": False,
    "source_attestation_required": True,
    "one_order_authorization_required": True,
    "atomic_authorization_reservation_required": True,
    "idempotency_required": True,
    "fresh_post_authorization_broker_state_required": True,
    "stale_price_guard_required": True,
    "spread_guard_required": True,
    "available_funds_guard_required": True,
    "position_no_short_guard_required": True,
    "append_only_attempt_journal_required": True,
    "reconciliation_before_retry_required": True,
    "kill_switch_required": True,
    "independent_implementation_review_required": True,
    "explicit_paper_execution_release_required": True,
    "explicit_live_execution_release_required": True,
}


def _digest(payload):
    try:
        encoded = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, OverflowError):
        return None
    return hashlib.sha256(encoded).hexdigest()


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


def _uuid4(value):
    text = str(value or "").strip()
    try:
        parsed = UUID(text)
    except (ValueError, AttributeError):
        return None
    return text if parsed.version == 4 and str(parsed) == text else None


def _utc_datetime(value):
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


def _permissions_false(payload):
    return (
        isinstance(payload, dict)
        and all(
            name in payload
            and payload.get(name) is False
            for name in PERMISSION_FLAGS
        )
    )


def _blocked(reason, checks=None):
    return {
        "engine": ENGINE_VERSION,
        "design_version": DESIGN_VERSION,
        "status": "BLOCKED",
        "reason": reason,
        "checks": checks or {},
        "design_validated": False,
        "source_attestation_revalidated": False,
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
        "next_gate": "REPAIR_NON_EXECUTABLE_ADAPTER_DESIGN",
    }


def evaluate_implementation_design(
    source_attestation,
    design_manifest,
    current_source_text,
    current_git_sha,
    repository_clean,
    now=None,
):
    now = (
        now.astimezone(timezone.utc)
        if isinstance(now, datetime)
        and now.tzinfo is not None
        else datetime.now(timezone.utc)
    )

    checks = {}

    def check(name, passed):
        checks[name] = bool(passed)

    source_attestation_ok = isinstance(
        source_attestation,
        dict,
    )
    manifest_ok = isinstance(
        design_manifest,
        dict,
    )
    check(
        "source_attestation_is_object",
        source_attestation_ok,
    )
    check(
        "design_manifest_is_object",
        manifest_ok,
    )

    source_attestation = (
        source_attestation
        if source_attestation_ok
        else {}
    )
    design_manifest = (
        design_manifest
        if manifest_ok
        else {}
    )

    check(
        "source_attestation_field_set_exact",
        set(source_attestation)
        == SOURCE_ATTESTATION_FIELDS,
    )
    check(
        "design_manifest_field_set_exact",
        set(design_manifest)
        == DESIGN_FIELDS,
    )

    source_checks = source_attestation.get(
        "checks"
    )
    source_checks_valid = (
        isinstance(source_checks, dict)
        and set(source_checks)
        == EXPECTED_SOURCE_ATTESTATION_CHECKS
        and all(
            source_checks.get(name) is True
            for name in EXPECTED_SOURCE_ATTESTATION_CHECKS
        )
    )
    check(
        "source_attestation_checks_exact_and_passed",
        source_checks_valid,
    )

    source_attestation_state = (
        source_attestation.get("engine")
        == SOURCE_ATTESTATION_ENGINE_VERSION
        and source_attestation.get("status")
        == "VERIFIED"
        and source_attestation.get("verified") is True
        and source_attestation.get(
            "adapter_source_independently_attested"
        )
        is True
        and source_attestation.get("reason")
        == "INDEPENDENT_SOURCE_REVIEW_ATTESTATION_VERIFIED"
        and source_attestation.get("next_gate")
        == "NON_EXECUTABLE_ADAPTER_IMPLEMENTATION_DESIGN_REVIEW_REQUIRED"
        and _permissions_false(
            source_attestation
        )
    )
    check(
        "source_attestation_state_verified_non_executable",
        source_attestation_state,
    )

    review_id = _uuid4(
        source_attestation.get("review_id")
    )
    check(
        "source_review_id_uuid4",
        review_id is not None,
    )
    check(
        "source_reviewer_id_present",
        isinstance(
            source_attestation.get(
                "reviewer_id"
            ),
            str,
        )
        and bool(
            source_attestation.get(
                "reviewer_id"
            ).strip()
        ),
    )

    for name in (
        "source_review_artifact_sha256",
        "review_request_sha256",
        "source_sha256",
        "source_policy_sha256",
        "source_attestation_sha256",
        "reviewer_evidence_sha256",
    ):
        check(
            f"{name}_valid",
            _sha256(
                source_attestation.get(
                    name
                )
            )
            is not None,
        )

    captured = _utc_datetime(
        source_attestation.get(
            "captured_at_utc"
        )
    )
    expires = _utc_datetime(
        source_attestation.get(
            "expires_at_utc"
        )
    )
    check(
        "source_attestation_time_window_valid",
        captured is not None
        and expires is not None
        and captured <= now <= expires,
    )

    current_git_sha = _git_sha(
        current_git_sha
    )
    check(
        "git_sha_bound",
        current_git_sha is not None
        and current_git_sha
        == _git_sha(
            source_attestation.get(
                "git_sha"
            )
        ),
    )
    check(
        "repository_clean",
        repository_clean is True,
    )

    current_source_sha256 = (
        hashlib.sha256(
            current_source_text.encode(
                "utf-8"
            )
        ).hexdigest()
        if isinstance(
            current_source_text,
            str,
        )
        and current_source_text
        else None
    )
    check(
        "current_source_bound_to_attestation",
        current_source_sha256 is not None
        and current_source_sha256
        == _sha256(
            source_attestation.get(
                "source_sha256"
            )
        ),
    )

    design_exact = (
        set(design_manifest)
        == DESIGN_FIELDS
        and all(
            design_manifest.get(name)
            == expected
            for name, expected
            in EXPECTED_DESIGN_VALUES.items()
        )
    )
    check(
        "design_manifest_exact_frozen_scope",
        design_exact,
    )

    design_sha256 = _digest(
        design_manifest
    )
    check(
        "design_manifest_canonical_digest_available",
        design_sha256 is not None,
    )

    failures = [
        name
        for name, passed in checks.items()
        if not passed
    ]
    if failures:
        return _blocked(
            "NON_EXECUTABLE_ADAPTER_DESIGN_INVALID",
            checks,
        )

    return {
        "engine": ENGINE_VERSION,
        "design_version": DESIGN_VERSION,
        "generated_at": now.isoformat(),
        "status": "IMPLEMENTATION_DESIGN_VALIDATED_NON_EXECUTABLE",
        "reason": "PAPER_ADAPTER_SCOPE_FROZEN_BEFORE_IMPLEMENTATION",
        "checks": checks,
        "design_validated": True,
        "source_attestation_revalidated": True,
        "source_attestation_sha256": (
            source_attestation[
                "source_attestation_sha256"
            ]
        ),
        "source_review_id": review_id,
        "source_reviewer_id": (
            source_attestation[
                "reviewer_id"
            ]
        ),
        "git_sha": current_git_sha,
        "source_sha256": (
            source_attestation[
                "source_sha256"
            ]
        ),
        "source_policy_sha256": (
            source_attestation[
                "source_policy_sha256"
            ]
        ),
        "runtime_prerequisite_sha256": (
            source_attestation[
                "source_review_artifact_sha256"
            ]
        ),
        "design_manifest_sha256": design_sha256,
        "design_manifest": design_manifest,
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
            "FRESH_POST_AUTHORIZATION_BROKER_STATE_RISK_REVIEW_REQUIRED"
        ),
    }
