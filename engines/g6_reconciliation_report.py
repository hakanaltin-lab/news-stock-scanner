"""Fail-closed, read-only G6 paper reconciliation report.

The report is diagnostic evidence only; it never grants permission to submit
an order. Broker provenance must be established outside this module.
"""
from datetime import datetime, timezone
from engines.g6_paper_reconciliation_runner import reconcile_journal


def build_g6_reconciliation_report(journal, broker_snapshot, *, expected_account_id, now=None):
    checked_at = now if now is not None else datetime.now(timezone.utc)
    if (not isinstance(checked_at, datetime) or checked_at.tzinfo is None
            or checked_at.utcoffset() is None):
        return {
            "schema_version": 1, "checked_at": None, "status": "BLOCKED",
            "execution_allowed": False, "live_execution_allowed": False,
            "paper_order_submission_allowed": False,
            "reason": "INVALID_REVIEW_TIMESTAMP", "matched_count": 0,
            "unresolved_count": 0, "unresolved_order_ids": [],
            "manual_review_required": True,
        }
    result = reconcile_journal(
        journal, broker_snapshot, expected_account_id=expected_account_id, now=checked_at
    )
    matched = result.get("matched", [])
    unresolved = result.get("unresolved", [])
    return {
        "schema_version": 1,
        "checked_at": checked_at.isoformat(),
        "status": "BLOCKED" if result.get("reason") != "READ_ONLY_RECONCILIATION" else "REVIEW_REQUIRED",
        "execution_allowed": False,
        "live_execution_allowed": False,
        "paper_order_submission_allowed": False,
        "reason": result.get("reason", "UNKNOWN_FAILURE"),
        "matched_count": len(matched) if isinstance(matched, list) else 0,
        "unresolved_count": len(unresolved) if isinstance(unresolved, list) else 0,
        "unresolved_order_ids": unresolved if isinstance(unresolved, list) else [],
        "manual_review_required": True,
    }
