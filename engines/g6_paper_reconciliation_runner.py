"""Offline, read-only journal-to-snapshot reconciliation orchestration.

Never connects to a broker or authorizes paper order submission.
"""
import sqlite3
from engines.g6_paper_reconciliation import reconcile_paper_snapshot


def reconcile_journal(journal, broker_snapshot, *, expected_account_id, now=None):
    if not isinstance(expected_account_id, str) or not expected_account_id.strip():
        return {"ready": False, "reason": "EXPECTED_PAPER_ACCOUNT_REQUIRED"}
    try:
        inventory = journal.list_unresolved()
    except (AttributeError, TypeError, ValueError, RuntimeError, OSError, sqlite3.Error):
        return {"ready": False, "reason": "JOURNAL_UNAVAILABLE"}
    if not isinstance(inventory, dict) or inventory.get("valid") is not True:
        return {"ready": False, "reason": "JOURNAL_UNAVAILABLE"}
    orders = inventory.get("orders")
    if not isinstance(orders, list) or any(
        not isinstance(item, dict)
        or item.get("status") not in ("RESERVED", "UNKNOWN")
        or not isinstance(item.get("client_order_id"), str)
        for item in orders
    ):
        return {"ready": False, "reason": "INVALID_JOURNAL_INVENTORY"}
    ids = [item["client_order_id"] for item in orders]
    if any(not key.strip() or key != key.strip() or len(key) > 128 for key in ids):
        return {"ready": False, "reason": "INVALID_JOURNAL_ORDER_REFERENCE"}
    if len(ids) != len(set(ids)):
        return {"ready": False, "reason": "DUPLICATE_JOURNAL_ORDER_REFERENCE"}
    return reconcile_paper_snapshot(
        ids,
        broker_snapshot,
        expected_account_id=expected_account_id,
        now=now,
    )
