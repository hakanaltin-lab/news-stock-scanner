"""Read-only IBKR paper snapshot normalization.

Accepts already-fetched data from a trusted broker adapter; never makes a
network request or infers account authenticity from a payload. A separate
authenticated transport must attest provenance and completeness.
"""
from datetime import datetime


def normalize_ibkr_paper_orders(raw_orders, *, account_id, captured_at=None,
                                transport_authenticated=False, complete=False):
    blocked = {"verified": False, "complete": False, "account_type": "UNVERIFIED",
               "account_id": account_id, "timestamp": None, "orders": [],
               "reason": "UNVERIFIED_BROKER_PROVENANCE"}
    if transport_authenticated is not True or complete is not True:
        return blocked
    if not isinstance(account_id, str) or not account_id.startswith("DU"):
        return {**blocked, "reason": "INVALID_PAPER_ACCOUNT"}
    if not isinstance(raw_orders, list):
        return {**blocked, "reason": "INVALID_BROKER_ORDERS"}
    normalized = []
    seen_order_refs = set()
    for item in raw_orders:
        if not isinstance(item, dict):
            return {**blocked, "reason": "INVALID_BROKER_ORDER"}
        order_id = item.get("orderRef")
        if not isinstance(order_id, str) or not order_id.strip() or len(order_id) > 128:
            return {**blocked, "reason": "MISSING_ORDER_REFERENCE"}
        if item.get("account") != account_id:
            return {**blocked, "reason": "ORDER_ACCOUNT_MISMATCH"}
        if order_id != order_id.strip():
            return {**blocked, "reason": "INVALID_ORDER_REFERENCE_WHITESPACE"}
        if order_id in seen_order_refs:
            return {**blocked, "reason": "DUPLICATE_BROKER_ORDER_REFERENCE"}
        seen_order_refs.add(order_id)
        normalized.append({"client_order_id": order_id})
    # Never fabricate freshness: capture time must come from the trusted caller.
    observed = captured_at
    if not isinstance(observed, datetime) or observed.tzinfo is None or observed.utcoffset() is None:
        return {**blocked, "reason": "INVALID_CAPTURE_TIMESTAMP"}
    return {"verified": True, "complete": True, "account_type": "PAPER",
            "account_id": account_id, "timestamp": observed.isoformat(),
            "orders": normalized, "reason": "NORMALIZED_READ_ONLY"}
