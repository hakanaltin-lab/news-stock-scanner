"""G6 Paper intent replay protection (offline only; never sends orders).

This module is a local preflight aid, NOT an execution authorization.
A durable store must be used before enabling any broker-side order placement.
"""
import hashlib
import json
import os
from pathlib import Path

def intent_fingerprint(account, order):
    """Bind a proposed order to the exact paper account and order fields."""
    if not isinstance(order, dict) or not account or not str(account).strip():
        raise ValueError("account and order are required")
    raw = json.dumps({"account": str(account).strip(), "order": order},
                     sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()

def inspect_intent(account, order, journal_path):
    """Fail closed if journal is absent, malformed, or contains matching intent.

    Inspection does not reserve an intent; caller must NOT treat PASS as
    permission to submit. Atomic reservation and broker reconciliation are
    separate prerequisites for a future execution connector.
    """
    fingerprint = intent_fingerprint(account, order)
    path = Path(journal_path)
    if not path.is_file():
        return {"status": "BLOCKED", "reason": "JOURNAL_NOT_INITIALIZED",
                "fingerprint": fingerprint, "broker_submission_allowed": False}
    try:
        with path.open(encoding="utf-8") as handle:
            entries = json.load(handle)
        if not isinstance(entries, list) or any(
            not isinstance(entry, dict) or not isinstance(entry.get("fingerprint"), str)
            for entry in entries
        ):
            raise ValueError("invalid journal")
    except (OSError, ValueError, TypeError):
        return {"status": "BLOCKED", "reason": "JOURNAL_UNREADABLE",
                "fingerprint": fingerprint, "broker_submission_allowed": False}
    duplicate = any(entry["fingerprint"] == fingerprint for entry in entries)
    return {"status": "BLOCKED" if duplicate else "INSPECTED_ONLY",
            "reason": "DUPLICATE_INTENT" if duplicate else "ATOMIC_RESERVATION_REQUIRED",
            "fingerprint": fingerprint, "broker_submission_allowed": False}
