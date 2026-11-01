"""G6.12 offline paper order intent preflight.

This module cannot connect to a broker or submit orders. Validation is
diagnostic only; every return explicitly denies execution.
"""
import math

ALLOWED_SIDES = frozenset(("BUY", "SELL"))
ALLOWED_TYPES = frozenset(("LMT",))


def validate_paper_intent(intent, context):
    base = {
        "status": "BLOCKED",
        "paper_order_submission_allowed": False,
        "live_trading_allowed": False,
    }
    if not isinstance(intent, dict) or not isinstance(context, dict):
        return {**base, "reason": "INVALID_INPUT"}
    if context.get("mode") != "PAPER" or context.get("live_trading_allowed") is not False:
        return {**base, "reason": "UNSAFE_MODE"}
    if context.get("broker_read_only") is not True:
        return {**base, "reason": "READ_ONLY_GUARD_MISSING"}
    if context.get("paper_account_verified") is not True:
        return {**base, "reason": "PAPER_ACCOUNT_UNVERIFIED"}
    if context.get("kill_switch_engaged") is not True:
        return {**base, "reason": "KILL_SWITCH_NOT_ENGAGED"}
    if intent.get("side") not in ALLOWED_SIDES:
        return {**base, "reason": "INVALID_SIDE"}
    if intent.get("order_type") not in ALLOWED_TYPES:
        return {**base, "reason": "UNSUPPORTED_ORDER_TYPE"}
    symbol = intent.get("symbol")
    if not isinstance(symbol, str) or not symbol.isascii() or not (1 <= len(symbol) <= 10) or not all(c.isupper() or c.isdigit() or c in ".-" for c in symbol):
        return {**base, "reason": "INVALID_SYMBOL"}
    quantity = intent.get("quantity")
    if type(quantity) is not int or not 1 <= quantity <= 100:
        return {**base, "reason": "INVALID_QUANTITY"}
    price = intent.get("limit_price")
    if type(price) not in (int, float) or not math.isfinite(price) or price <= 0:
        return {**base, "reason": "INVALID_LIMIT_PRICE"}
    if price * quantity > 500:
        return {**base, "reason": "NOTIONAL_CAP_EXCEEDED"}
    key = intent.get("idempotency_key")
    if not isinstance(key, str) or not (8 <= len(key) <= 128) or not key.isascii() or not all(c.isalnum() or c in "-_" for c in key):
        return {**base, "reason": "INVALID_IDEMPOTENCY_KEY"}
    return {
        **base,
        "status": "VALIDATED_READ_ONLY",
        "reason": "DIAGNOSTIC_ONLY_NO_EXECUTION",
        "symbol": symbol,
        "side": intent["side"],
        "quantity": quantity,
        "limit_price": price,
    }
