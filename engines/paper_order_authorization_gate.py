"""AURORA G5 manual Paper authorization preflight.

This gate validates a short-lived, one-order human authorization artifact
against the exact G0-G4 completion status and exact G4 shadow order.

It intentionally has no broker dependency and never permits order submission.
A successful result means only that the authorization evidence is internally
consistent and may be presented to a separately reviewed Paper execution
connector in a later gate.
"""

from datetime import datetime, timezone
import hashlib
import hmac
import json
from uuid import UUID


AUTH_VERSION = "AURORA_G5_PAPER_AUTHORIZATION_V2"
DEFAULT_MAX_AUTH_AGE_SECONDS = 600

REQUIRED_COMPLETION_CHECKS = {
    "g0_g1_verified",
    "g0_g1_evidence_current",
    "g0_control_plane_instance_bound_to_gateway_attestation",
    "g0_signed_proof_digest_bound",
    "g2_g3_ready",
    "g0_g1_readiness_proof_bound",
    "g2_gateway_read_only_independently_attested",
    "gateway_attestation_runtime_verified",
    "gateway_attestation_g2_runtime_bound",
    "gateway_attestation_readiness_bound",
    "g2_readiness_proof_bound",
    "g2_g3_evidence_fresh",
    "g4_shadow_accepted",
    "g4_shadow_order_payload_valid",
    "g4_shadow_order_ledger_payload_bound",
    "g4_evidence_fresh",
    "g4_readiness_proof_bound",
    "g4_evidence_run_bound",
    "shadow_ledger_verified",
    "g4_ledger_receipt_bound",
    "ledger_audit_fresh",
}

AUTHORIZATION_FIELDS = {
    "version",
    "authorization_id",
    "approved",
    "mode",
    "scope",
    "issued_at",
    "expires_at",
    "completion_status_sha256",
    "shadow_order_sha256",
    "broker_submission_allowed",
    "paper_order_submission_allowed",
    "live_execution_allowed",
    "automatic_promotion_allowed",
    "real_money_trading_allowed",
}


def _digest(payload):
    canonical = json.dumps(
        payload or {},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


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


def _uuid4(value):
    text = str(value or "").strip()
    try:
        parsed = UUID(text)
    except (ValueError, AttributeError):
        return None
    return text if parsed.version == 4 and str(parsed) == text else None


def _sha256_text(value):
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


def _instance_id(value):
    text = str(value or "").strip()
    if (
        not text.isdigit()
        or not 6 <= len(text) <= 30
        or text[0] == "0"
    ):
        return None
    return text


def _safe_flags(payload):
    required = (
        "broker_submission_allowed",
        "paper_order_submission_allowed",
        "live_execution_allowed",
        "automatic_promotion_allowed",
        "real_money_trading_allowed",
    )
    return all(
        name in payload and payload.get(name) is False
        for name in required
    )


def _block(reason, checks=None):
    return {
        "engine": "AURORA G5 Manual Paper Authorization Preflight",
        "status": "BLOCKED",
        "reason": reason,
        "checks": checks or {},
        "broker_submission_allowed": False,
        "paper_order_submission_allowed": False,
        "live_execution_allowed": False,
        "automatic_promotion_allowed": False,
        "real_money_trading_allowed": False,
    }


def evaluate_manual_paper_authorization(
    completion_status,
    shadow_order,
    authorization,
    now=None,
    max_auth_age_seconds=DEFAULT_MAX_AUTH_AGE_SECONDS,
):
    now = _utc_datetime(now) or datetime.now(timezone.utc)
    completion_status = completion_status or {}
    shadow_order = shadow_order or {}
    authorization = authorization or {}

    issued_at = _utc_datetime(authorization.get("issued_at"))
    expires_at = _utc_datetime(authorization.get("expires_at"))
    authorization_id = _uuid4(authorization.get("authorization_id"))

    auth_age = None
    if issued_at is not None:
        auth_age = (now - issued_at).total_seconds()

    lifetime = None
    if issued_at is not None and expires_at is not None:
        lifetime = (expires_at - issued_at).total_seconds()

    completion_digest = _digest(completion_status)
    shadow_digest = _digest(shadow_order)
    completion_checks = (
        completion_status.get("checks")
        if isinstance(
            completion_status.get("checks"),
            dict,
        )
        else {}
    )
    completion_binding = (
        completion_status.get("evidence_binding")
        if isinstance(
            completion_status.get("evidence_binding"),
            dict,
        )
        else {}
    )

    readiness_run_id = _uuid4(
        completion_binding.get(
            "readiness_evidence_run_id"
        )
    )
    g4_run_id = _uuid4(
        completion_binding.get(
            "g4_evidence_run_id"
        )
    )
    gce_instance_id = _instance_id(
        completion_binding.get(
            "gce_instance_id"
        )
    )

    g0_digest = _sha256_text(
        completion_binding.get(
            "g0_g1_proof_sha256"
        )
    )
    recorded_g0_digest = _sha256_text(
        completion_binding.get(
            "readiness_recorded_g0_g1_proof_sha256"
        )
    )
    g2_digest = _sha256_text(
        completion_binding.get(
            "g2_paper_read_only_proof_sha256"
        )
    )
    recorded_g2_digest = _sha256_text(
        completion_binding.get(
            "readiness_recorded_g2_proof_sha256"
        )
    )
    g2_attestation_digest = _sha256_text(
        completion_binding.get(
            "g2_gateway_read_only_attestation_sha256"
        )
    )
    runtime_attestation_digest = _sha256_text(
        completion_binding.get(
            "runtime_gateway_read_only_attestation_sha256"
        )
    )
    readiness_attestation_digest = _sha256_text(
        completion_binding.get(
            "readiness_recorded_gateway_attestation_sha256"
        )
    )
    readiness_digest = _sha256_text(
        completion_binding.get(
            "readiness_proof_sha256"
        )
    )
    g4_recorded_readiness_digest = _sha256_text(
        completion_binding.get(
            "g4_recorded_readiness_proof_sha256"
        )
    )
    completion_shadow_digest = _sha256_text(
        completion_binding.get(
            "g4_shadow_order_sha256"
        )
    )
    ledger_payload_digest = _sha256_text(
        completion_binding.get(
            "g4_ledger_payload_sha256"
        )
    )
    recomputed_ledger_payload_digest = _sha256_text(
        completion_binding.get(
            "g4_recomputed_ledger_payload_sha256"
        )
    )
    ledger_receipt_digest = _sha256_text(
        completion_binding.get(
            "g4_ledger_receipt_sha256"
        )
    )
    audited_ledger_receipt_digest = _sha256_text(
        completion_binding.get(
            "audited_ledger_receipt_sha256"
        )
    )

    completion_checks_exact = (
        set(completion_checks)
        ==
        REQUIRED_COMPLETION_CHECKS
        and all(
            completion_checks.get(name) is True
            for name in REQUIRED_COMPLETION_CHECKS
        )
    )

    completion_runtime_binding_valid = (
        readiness_run_id is not None
        and readiness_run_id == g4_run_id
        and gce_instance_id is not None
        and g0_digest is not None
        and g0_digest == recorded_g0_digest
        and g2_digest is not None
        and g2_digest == recorded_g2_digest
        and g2_attestation_digest is not None
        and g2_attestation_digest
        == runtime_attestation_digest
        == readiness_attestation_digest
        and readiness_digest is not None
        and readiness_digest
        == g4_recorded_readiness_digest
        and completion_shadow_digest is not None
        and ledger_payload_digest is not None
        and ledger_payload_digest
        == recomputed_ledger_payload_digest
        and ledger_receipt_digest is not None
        and ledger_receipt_digest
        == audited_ledger_receipt_digest
    )

    checks = {
        "authorization_field_set_exact": (
            set(authorization) == AUTHORIZATION_FIELDS
        ),
        "completion_validated_shadow_only": (
            completion_status.get("engine")
            == "AURORA V8.9.29 G0-G4 Completion Gate"
            and completion_status.get("status")
            == "PAPER_RUNTIME_VALIDATED_SHADOW_ONLY"
            and completion_status.get("next_gate")
            == "MANUAL_PAPER_ORDER_AUTHORIZATION_NOT_GRANTED"
            and completion_status.get("failure_reasons") == []
            and _safe_flags(completion_status)
        ),
        "completion_check_set_exact_and_passed": (
            completion_checks_exact
        ),
        "completion_runtime_binding_valid": (
            completion_runtime_binding_valid
        ),
        "shadow_order_accepted": (
            shadow_order.get("status") == "SHADOW_ACCEPTED"
            and _safe_flags(shadow_order)
        ),
        "authorization_version": (
            authorization.get("version") == AUTH_VERSION
        ),
        "explicit_human_approval": (
            authorization.get("approved") is True
        ),
        "paper_mode_only": (
            str(authorization.get("mode") or "").upper() == "PAPER"
        ),
        "single_order_scope": (
            authorization.get("scope") == "ONE_PAPER_ORDER"
        ),
        "authorization_id_uuid4": authorization_id is not None,
        "authorization_current": (
            auth_age is not None
            and auth_age >= -2
            and auth_age <= float(max_auth_age_seconds)
            and expires_at is not None
            and expires_at >= now
            and lifetime is not None
            and lifetime > 0
            and lifetime <= float(max_auth_age_seconds)
        ),
        "completion_digest_bound": hmac.compare_digest(
            str(authorization.get("completion_status_sha256") or "").lower(),
            completion_digest,
        ),
        "shadow_order_digest_bound": hmac.compare_digest(
            str(authorization.get("shadow_order_sha256") or "").lower(),
            shadow_digest,
        ),
        "completion_shadow_order_digest_bound": (
            completion_shadow_digest is not None
            and hmac.compare_digest(
                completion_shadow_digest,
                shadow_digest,
            )
        ),
        "authorization_permissions_non_executable": (
            _safe_flags(authorization)
        ),
    }

    failures = [name for name, passed in checks.items() if not passed]
    if failures:
        return _block("MANUAL_PAPER_AUTHORIZATION_INVALID", checks)

    return {
        "engine": "AURORA G5 Manual Paper Authorization Preflight",
        "generated_at": now.isoformat(),
        "status": "MANUAL_PAPER_AUTHORIZATION_VALIDATED",
        "authorization_id": authorization_id,
        "scope": "ONE_PAPER_ORDER",
        "mode": "PAPER",
        "authorization_issued_at": issued_at.isoformat(),
        "authorization_expires_at": expires_at.isoformat(),
        "authorization_version": AUTH_VERSION,
        "authorization_artifact_sha256": _digest(
            authorization
        ),
        "completion_status_sha256": completion_digest,
        "shadow_order_sha256": shadow_digest,
        "evidence_run_id": readiness_run_id,
        "gce_instance_id": gce_instance_id,
        "g0_g1_proof_sha256": g0_digest,
        "g2_paper_read_only_proof_sha256": g2_digest,
        "gateway_read_only_attestation_sha256": (
            runtime_attestation_digest
        ),
        "readiness_proof_sha256": readiness_digest,
        "g4_ledger_receipt_sha256": ledger_receipt_digest,
        "checks": checks,
        "authorization_can_be_consumed_once": True,
        "authorization_is_pre_execution_only": True,
        "broker_submission_allowed": False,
        "paper_order_submission_allowed": False,
        "live_execution_allowed": False,
        "automatic_promotion_allowed": False,
        "real_money_trading_allowed": False,
        "next_gate": "PAPER_EXECUTION_CONNECTOR_REVIEW_REQUIRED",
    }
