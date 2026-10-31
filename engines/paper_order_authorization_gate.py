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


AUTH_VERSION = "AURORA_G5_PAPER_AUTHORIZATION_V1"
DEFAULT_MAX_AUTH_AGE_SECONDS = 600


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


def _safe_flags(payload):
    return all(
        payload.get(name) is False
        for name in (
            "broker_submission_allowed",
            "paper_order_submission_allowed",
            "live_execution_allowed",
            "automatic_promotion_allowed",
        )
        if name in payload
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

    checks = {
        "completion_validated_shadow_only": (
            completion_status.get("status")
            == "PAPER_RUNTIME_VALIDATED_SHADOW_ONLY"
            and completion_status.get("next_gate")
            == "MANUAL_PAPER_ORDER_AUTHORIZATION_NOT_GRANTED"
            and _safe_flags(completion_status)
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
        "no_live_or_automatic_promotion": (
            authorization.get("live_execution_allowed") is False
            and authorization.get("automatic_promotion_allowed") is False
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
        "completion_status_sha256": completion_digest,
        "shadow_order_sha256": shadow_digest,
        "checks": checks,
        "authorization_can_be_consumed_once": True,
        "broker_submission_allowed": False,
        "paper_order_submission_allowed": False,
        "live_execution_allowed": False,
        "automatic_promotion_allowed": False,
        "real_money_trading_allowed": False,
        "next_gate": "PAPER_EXECUTION_CONNECTOR_REVIEW_REQUIRED",
    }
