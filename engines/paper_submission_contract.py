"""G6.13 offline Paper submission contract.

This module only cross-validates reviewed artifacts. It has no broker
dependency and never grants Paper or Live submission permission.
"""

from datetime import datetime, timezone
import hashlib
import hmac
import json
import math
from uuid import UUID

from engines.paper_intent_preflight import REQUIRED_INTENT_FIELDS


DEFAULT_MAX_AUTH_RESULT_AGE_SECONDS = 120


def _digest(payload):
    encoded = json.dumps(
        payload or {},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


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


def _safe_authorization_flags(payload):
    return all(
        payload.get(name) is False
        for name in (
            "broker_submission_allowed",
            "paper_order_submission_allowed",
            "live_execution_allowed",
            "automatic_promotion_allowed",
            "real_money_trading_allowed",
        )
    )


def _normalize_intent(intent):
    if not isinstance(intent, dict) or set(intent) != REQUIRED_INTENT_FIELDS:
        return None

    symbol = intent.get("symbol")
    side = intent.get("side")
    order_type = intent.get("order_type")
    quantity = intent.get("quantity")
    price = intent.get("limit_price")
    key = intent.get("idempotency_key")

    if (not isinstance(symbol, str) or not symbol.isascii()
            or not (1 <= len(symbol) <= 10)
            or not all(c.isupper() or c.isdigit() or c in ".-" for c in symbol)):
        return None
    if side not in ("BUY", "SELL") or order_type != "LMT":
        return None
    if type(quantity) is not int or not (1 <= quantity <= 100):
        return None
    if type(price) not in (int, float) or not math.isfinite(price) or price <= 0:
        return None
    if price * quantity > 500:
        return None
    if (not isinstance(key, str) or not (8 <= len(key) <= 128)
            or not key.isascii()
            or not all(c.isalnum() or c in "-_" for c in key)):
        return None

    return {
        "symbol": symbol,
        "side": side,
        "order_type": order_type,
        "quantity": quantity,
        "limit_price": float(price),
        "idempotency_key": key,
    }


def _block(reason, checks=None):
    return {
        "engine": "AURORA G6.13 Paper Submission Contract",
        "status": "BLOCKED",
        "reason": reason,
        "checks": checks or {},
        "broker_submission_allowed": False,
        "paper_order_submission_allowed": False,
        "live_execution_allowed": False,
        "automatic_promotion_allowed": False,
        "real_money_trading_allowed": False,
        "broker_order_object_allowed": False,
    }


def evaluate_paper_submission_contract(
    authorization_result,
    risk_result,
    intent,
    shadow_order,
    consumed_authorization_ids,
    now=None,
    max_auth_result_age_seconds=DEFAULT_MAX_AUTH_RESULT_AGE_SECONDS,
):
    authorization_result = authorization_result or {}
    risk_result = risk_result or {}
    shadow_order = shadow_order or {}
    normalized = _normalize_intent(intent)
    now = _utc_datetime(now) or datetime.now(timezone.utc)

    generated_at = _utc_datetime(authorization_result.get("generated_at"))
    age = None
    if generated_at is not None:
        age = (now - generated_at).total_seconds()

    authorization_id = _uuid4(authorization_result.get("authorization_id"))

    replay_history_valid = (
        isinstance(consumed_authorization_ids, (list, tuple, set))
        and all(isinstance(item, str) and item.strip()
                for item in consumed_authorization_ids)
        and len(consumed_authorization_ids) == len(set(consumed_authorization_ids))
    )

    intent_sha256 = _digest(normalized) if normalized is not None else None
    shadow_sha256 = _digest(shadow_order)

    shadow_flags_safe = all(
        shadow_order.get(name) is False
        for name in (
            "broker_submission_allowed",
            "paper_order_submission_allowed",
            "live_execution_allowed",
        )
    ) and shadow_order.get("automatic_promotion_allowed") is not True

    shadow_fields_match = (
        normalized is not None
        and shadow_order.get("status") == "SHADOW_ACCEPTED"
        and shadow_order.get("symbol") == normalized["symbol"]
        and shadow_order.get("action") == normalized["side"]
        and shadow_order.get("quantity") == normalized["quantity"]
        and shadow_order.get("order_type") == "LIMIT"
        and shadow_order.get("time_in_force") == "DAY"
        and shadow_order.get("asset_type") == "STK"
        and shadow_order.get("idempotency_key") == normalized["idempotency_key"]
        and type(shadow_order.get("limit_price")) in (int, float)
        and math.isfinite(shadow_order.get("limit_price"))
        and math.isclose(
            float(shadow_order.get("limit_price")),
            normalized["limit_price"],
            rel_tol=1e-12,
            abs_tol=1e-7,
        )
    )

    checks = {
        "authorization_validated": (
            authorization_result.get("status")
            == "MANUAL_PAPER_AUTHORIZATION_VALIDATED"
            and authorization_result.get("mode") == "PAPER"
            and authorization_result.get("scope") == "ONE_PAPER_ORDER"
            and authorization_result.get("next_gate")
            == "PAPER_EXECUTION_CONNECTOR_REVIEW_REQUIRED"
            and authorization_result.get("authorization_can_be_consumed_once") is True
            and _safe_authorization_flags(authorization_result)
        ),
        "authorization_id_uuid4": authorization_id is not None,
        "authorization_result_fresh": (
            age is not None
            and age >= -2
            and age <= float(max_auth_result_age_seconds)
        ),
        "replay_history_valid": replay_history_valid,
        "authorization_not_previously_consumed": (
            replay_history_valid
            and authorization_id is not None
            and authorization_id not in set(consumed_authorization_ids)
        ),
        "intent_schema_valid": normalized is not None,
        "risk_validated_read_only": (
            risk_result.get("status") == "VALIDATED_READ_ONLY"
            and risk_result.get("reason")
            == "PORTFOLIO_DIAGNOSTIC_ONLY_NO_EXECUTION"
            and risk_result.get("paper_order_submission_allowed") is False
            and risk_result.get("live_trading_allowed") is False
        ),
        "risk_intent_digest_bound": (
            intent_sha256 is not None
            and isinstance(risk_result.get("intent_sha256"), str)
            and hmac.compare_digest(
                risk_result.get("intent_sha256"),
                intent_sha256,
            )
        ),
        "risk_idempotency_bound": (
            normalized is not None
            and risk_result.get("idempotency_key")
            == normalized["idempotency_key"]
        ),
        "shadow_digest_bound_to_authorization": (
            isinstance(authorization_result.get("shadow_order_sha256"), str)
            and hmac.compare_digest(
                authorization_result.get("shadow_order_sha256"),
                shadow_sha256,
            )
        ),
        "shadow_submission_flags_safe": shadow_flags_safe,
        "shadow_execution_fields_match_intent": shadow_fields_match,
    }

    failures = [name for name, passed in checks.items() if not passed]
    if failures:
        return _block("SUBMISSION_CONTRACT_INVALID", checks)

    contract_payload = {
        "authorization_id": authorization_id,
        "intent_sha256": intent_sha256,
        "shadow_order_sha256": shadow_sha256,
        "idempotency_key": normalized["idempotency_key"],
    }

    return {
        **_block("VALIDATED_NON_EXECUTABLE", checks),
        "status": "SUBMISSION_CONTRACT_VALIDATED_NON_EXECUTABLE",
        "reason": "ARTIFACTS_BOUND_BUT_BROKER_PERMISSION_NOT_GRANTED",
        "authorization_id": authorization_id,
        "intent_sha256": intent_sha256,
        "shadow_order_sha256": shadow_sha256,
        "idempotency_key": normalized["idempotency_key"],
        "contract_sha256": _digest(contract_payload),
        "authorization_id_must_be_atomically_consumed_before_submission": True,
        "next_gate": "PAPER_BROKER_ADAPTER_CODE_REVIEW_REQUIRED",
    }
