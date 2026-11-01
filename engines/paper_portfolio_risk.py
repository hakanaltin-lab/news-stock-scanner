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


def _valid_symbol(value):
    return (isinstance(value, str) and value.isascii() and 1 <= len(value) <= 10
            and all(c.isupper() or c.isdigit() or c in ".-" for c in value))


def _valid_idempotency_key(value):
    return (isinstance(value, str) and 8 <= len(value) <= 128 and value.isascii()
            and all(c.isalnum() or c in "-_" for c in value))


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


def _reconcile_pending_orders(portfolio):
    pending_orders = portfolio.get("pending_orders")
    if not isinstance(pending_orders, list):
        return None, "MISSING_PENDING_ORDER_EVIDENCE"

    seen_keys = set()
    pending_sell_quantity = {}
    computed_notional = 0.0
    for row in pending_orders:
        if not isinstance(row, dict):
            return None, "INVALID_PENDING_ORDER"
        key = row.get("idempotency_key")
        symbol = row.get("symbol")
        side = row.get("side")
        quantity = row.get("quantity")
        price = row.get("limit_price")
        if not _valid_idempotency_key(key):
            return None, "INVALID_PENDING_ORDER_IDEMPOTENCY"
        if key in seen_keys:
            return None, "DUPLICATE_PENDING_ORDER_IDEMPOTENCY"
        seen_keys.add(key)
        if not _valid_symbol(symbol) or side not in ("BUY", "SELL"):
            return None, "INVALID_PENDING_ORDER_IDENTITY"
        if type(quantity) is not int or quantity <= 0:
            return None, "INVALID_PENDING_ORDER_QUANTITY"
        if type(price) not in (int, float) or not math.isfinite(price) or price <= 0:
            return None, "INVALID_PENDING_ORDER_PRICE"
        computed_notional += quantity * price
        if side == "SELL":
            pending_sell_quantity[symbol] = pending_sell_quantity.get(symbol, 0) + quantity

    claimed_notional = portfolio.get("pending_notional_usd")
    if not _nonnegative_number(claimed_notional):
        return None, "INVALID_PORTFOLIO_VALUES"
    if not math.isclose(computed_notional, claimed_notional, rel_tol=1e-12, abs_tol=1e-7):
        return None, "PENDING_NOTIONAL_MISMATCH"

    return {
        "keys": seen_keys,
        "pending_notional_usd": computed_notional,
        "pending_sell_quantity_by_symbol": pending_sell_quantity,
    }, None


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
    if not all(_nonnegative_number(x) for x in (equity, gross)) or equity <= 0:
        return {**base, "reason": "INVALID_PORTFOLIO_VALUES"}

    pending_state, pending_error = _reconcile_pending_orders(portfolio)
    if pending_error:
        return {**base, "reason": pending_error}

    keys = portfolio.get("known_idempotency_keys")
    if not isinstance(keys, (list, tuple, set)) or not all(isinstance(k, str) for k in keys):
        return {**base, "reason": "INVALID_IDEMPOTENCY_HISTORY"}
    if len(keys) != len(set(keys)):
        return {**base, "reason": "CORRUPTED_IDEMPOTENCY_HISTORY"}
    if intent["idempotency_key"] in keys or intent["idempotency_key"] in pending_state["keys"]:
        return {**base, "reason": "DUPLICATE_ORDER_INTENT"}

    if intent["side"] == "SELL":
        positions = portfolio.get("positions_by_symbol")
        if not isinstance(positions, dict):
            return {**base, "reason": "MISSING_SELL_POSITION_EVIDENCE"}
        if not all(_valid_symbol(k) and type(v) is int and v >= 0
                   for k, v in positions.items()):
            return {**base, "reason": "INVALID_SELL_POSITION_EVIDENCE"}
        symbol = intent["symbol"]
        if symbol not in positions:
            return {**base, "reason": "UNKNOWN_SELL_POSITION"}
        pending_sell = pending_state["pending_sell_quantity_by_symbol"].get(symbol, 0)
        available = positions[symbol] - pending_sell
        if available < intent["quantity"]:
            return {**base, "reason": "INSUFFICIENT_AVAILABLE_SHARES"}

    # BUY is conservatively counted against exposure. SELL does not receive
    # automatic exposure relief because holdings and fills are unverified here.
    new_notional = intent["quantity"] * intent["limit_price"]
    pending = pending_state["pending_notional_usd"]
    proposed = gross + pending + (new_notional if intent["side"] == "BUY" else 0)
    if proposed > equity:
        return {**base, "reason": "EXPOSURE_EXCEEDS_EQUITY"}
    return {**base, "status": "VALIDATED_READ_ONLY",
            "reason": "PORTFOLIO_DIAGNOSTIC_ONLY_NO_EXECUTION",
            "projected_gross_exposure_usd": proposed,
            "snapshot_age_seconds": age}
