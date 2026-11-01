"""Offline portfolio and idempotency risk checks for G6.12.

No network, broker integration, persistence or order submission. Snapshot
must be supplied by caller; missing, stale or identity-mismatched data fails closed.
"""
import math
from datetime import datetime, timezone
from engines.paper_intent_preflight import validate_paper_intent

MAX_SNAPSHOT_AGE_SECONDS = 60


def _nonnegative_number(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def _parse_utc_timestamp(value):
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def evaluate_portfolio_intent(intent, context, portfolio, now_utc=None):
    base = {"status": "BLOCKED", "paper_order_submission_allowed": False,
            "live_trading_allowed": False}
    preliminary = validate_paper_intent(intent, context)
    if preliminary["status"] != "VALIDATED_READ_ONLY":
        return {**base, "reason": preliminary["reason"]}
    if not isinstance(portfolio, dict):
        return {**base, "reason": "MISSING_PORTFOLIO_SNAPSHOT"}
    if portfolio.get("snapshot_verified") is not True or portfolio.get("snapshot_fresh") is not True:
        return {**base, "reason": "UNVERIFIED_OR_STALE_PORTFOLIO"}

    expected_account = context.get("paper_account_fingerprint")
    observed_account = portfolio.get("paper_account_fingerprint")
    if (not isinstance(expected_account, str) or not expected_account.strip()
            or not isinstance(observed_account, str) or not observed_account.strip()
            or observed_account != expected_account):
        return {**base, "reason": "PORTFOLIO_ACCOUNT_MISMATCH"}

    generated_at = _parse_utc_timestamp(portfolio.get("snapshot_generated_at_utc"))
    if generated_at is None:
        return {**base, "reason": "INVALID_SNAPSHOT_TIMESTAMP"}
    current = now_utc if now_utc is not None else datetime.now(timezone.utc)
    if not isinstance(current, datetime) or current.tzinfo is None:
        return {**base, "reason": "INVALID_EVALUATION_TIME"}
    current = current.astimezone(timezone.utc)
    age = (current - generated_at).total_seconds()
    if age < 0 or age > MAX_SNAPSHOT_AGE_SECONDS:
        return {**base, "reason": "SNAPSHOT_TIMESTAMP_STALE"}

    equity = portfolio.get("equity_usd")
    gross = portfolio.get("gross_exposure_usd")
    pending = portfolio.get("pending_notional_usd")
    if not all(_nonnegative_number(x) for x in (equity, gross, pending)) or equity <= 0:
        return {**base, "reason": "INVALID_PORTFOLIO_VALUES"}
    keys = portfolio.get("known_idempotency_keys")
    if not isinstance(keys, (list, tuple, set)) or not all(isinstance(k, str) for k in keys):
        return {**base, "reason": "INVALID_IDEMPOTENCY_HISTORY"}
    if len(keys) != len(set(keys)):
        return {**base, "reason": "CORRUPTED_IDEMPOTENCY_HISTORY"}
    if intent["idempotency_key"] in keys:
        return {**base, "reason": "DUPLICATE_ORDER_INTENT"}
    # BUY is conservatively counted against exposure. SELL does not receive
    # automatic exposure relief because holdings and fills are unverified here.
    new_notional = intent["quantity"] * intent["limit_price"]
    proposed = gross + pending + (new_notional if intent["side"] == "BUY" else 0)
    if proposed > equity:
        return {**base, "reason": "EXPOSURE_EXCEEDS_EQUITY"}
    return {**base, "status": "VALIDATED_READ_ONLY",
            "reason": "PORTFOLIO_DIAGNOSTIC_ONLY_NO_EXECUTION",
            "projected_gross_exposure_usd": proposed,
            "snapshot_age_seconds": age}
