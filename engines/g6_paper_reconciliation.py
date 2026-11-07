"""Read-only reconciliation of local paper intents against a broker snapshot.

This module does not connect to IBKR, mutate the journal, or submit orders.
A snapshot must be explicitly verified as complete, fresh and from PAPER.
Missing orders are UNKNOWN, never proof that an order did not execute.
"""
from datetime import datetime, timezone


def reconcile_paper_snapshot(local_order_ids, snapshot, *, now=None, max_age_seconds=30, expected_account_id=None):
    blocked = {"ready": False, "matched": [], "unresolved": [], "reason": None}
    if not isinstance(snapshot, dict):
        return {**blocked, "reason": "INVALID_SNAPSHOT"}
    if snapshot.get("account_type") != "PAPER":
        return {**blocked, "reason": "UNVERIFIED_PAPER_ACCOUNT"}
    # A self-declared PAPER label is insufficient when an expected broker
    # account identifier is available. Refuse missing or mismatched identity.
    if expected_account_id is not None:
        if (not isinstance(expected_account_id, str) or not expected_account_id.strip()
                or snapshot.get("account_id") != expected_account_id):
            return {**blocked, "reason": "BROKER_ACCOUNT_MISMATCH"}
    if snapshot.get("complete") is not True or snapshot.get("verified") is not True:
        return {**blocked, "reason": "INCOMPLETE_OR_UNVERIFIED_SNAPSHOT"}
    timestamp = snapshot.get("timestamp")
    try:
        observed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        if observed.tzinfo is None:
            raise ValueError("naive timestamp")
        reference = now or datetime.now(timezone.utc)
        age = (reference - observed).total_seconds()
        if not 0 <= age <= max_age_seconds:
            raise ValueError("stale or future timestamp")
    except (ValueError, TypeError, AttributeError):
        return {**blocked, "reason": "STALE_OR_INVALID_SNAPSHOT"}
    orders = snapshot.get("orders")
    if not isinstance(orders, list) or any(
        not isinstance(order, dict) or not isinstance(order.get("client_order_id"), str)
        for order in orders
    ):
        return {**blocked, "reason": "INVALID_ORDER_LIST"}
    ids = [order["client_order_id"] for order in orders]
    if len(ids) != len(set(ids)):
        return {**blocked, "reason": "DUPLICATE_BROKER_ORDER_IDS"}
    if not isinstance(local_order_ids, (list, tuple, set)) or any(
        not isinstance(key, str) or not key for key in local_order_ids
    ):
        return {**blocked, "reason": "INVALID_LOCAL_ORDER_IDS"}
    if len(local_order_ids) != len(set(local_order_ids)):
        return {**blocked, "reason": "DUPLICATE_LOCAL_ORDER_IDS"}
    broker_ids = set(ids)
    matched = sorted(set(local_order_ids) & broker_ids)
    unresolved = sorted(set(local_order_ids) - broker_ids)
    # Even a clean snapshot cannot arm order submission; human-reviewed
    # broker reconciliation and separate authorization are still required.
    return {
        "ready": False,
        "matched": matched,
        "unresolved": unresolved,
        "reason": "UNRESOLVED_LOCAL_ORDERS" if unresolved else "READ_ONLY_RECONCILIATION",
    }
