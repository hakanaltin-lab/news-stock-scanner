"""Offline portfolio and idempotency risk checks for G6.12.

No network, broker integration, persistence or order submission. Snapshot
must be supplied by caller; missing/stale data always fails closed.
"""
import math
from engines.paper_intent_preflight import validate_paper_intent


def _nonnegative_number(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def evaluate_portfolio_intent(intent, context, portfolio):
    base = {"status": "BLOCKED", "paper_order_submission_allowed": False,
            "live_trading_allowed": False}
    preliminary = validate_paper_intent(intent, context)
    if preliminary["status"] != "VALIDATED_READ_ONLY":
        return {**base, "reason": preliminary["reason"]}
    if not isinstance(portfolio, dict):
        return {**base, "reason": "MISSING_PORTFOLIO_SNAPSHOT"}
    if portfolio.get("snapshot_verified") is not True or portfolio.get("snapshot_fresh") is not True:
        return {**base, "reason": "UNVERIFIED_OR_STALE_PORTFOLIO"}
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
            "projected_gross_exposure_usd": proposed}
