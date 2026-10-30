"""AURORA V8.9.27 IBKR paper-account identity guard.

The raw IBKR account identifier is accepted only from process memory/environment.
This module never returns or logs raw account identifiers.
"""

import hashlib
import os


ENV_NAME = "AURORA_IBKR_PAPER_ACCOUNT_ALLOWLIST"


def account_fingerprint(account):
    """Return the existing sanitized account token without exposing the ID."""
    if not account:
        return None
    digest = hashlib.sha256(str(account).encode("utf-8")).hexdigest()[:10]
    return f"IBKR-{digest.upper()}"


def load_paper_account_allowlist():
    raw = os.getenv(ENV_NAME, "")
    return {
        item.strip()
        for item in raw.split(",")
        if item.strip()
    }


def evaluate_paper_account_identity(accounts):
    accounts = [
        str(item).strip()
        for item in (accounts or [])
        if str(item).strip()
    ]
    allowlist = load_paper_account_allowlist()

    configured = bool(allowlist)
    received = bool(accounts)
    all_allowlisted = (
        configured
        and received
        and all(account in allowlist for account in accounts)
    )
    verified_fingerprints = (
        sorted({account_fingerprint(account) for account in accounts})
        if all_allowlisted
        else []
    )

    if not configured:
        reason = "PAPER_ACCOUNT_ALLOWLIST_NOT_CONFIGURED"
    elif not received:
        reason = "NO_MANAGED_ACCOUNT_RECEIVED"
    elif not all_allowlisted:
        reason = "PAPER_ACCOUNT_NOT_ALLOWLISTED"
    else:
        reason = "PAPER_ACCOUNT_VERIFIED"

    return {
        "allowlist_configured": configured,
        "managed_account_received": received,
        "account_count": len(accounts),
        "all_accounts_allowlisted": all_allowlisted,
        "paper_account_verified": all_allowlisted,
        "verified_account_fingerprints": verified_fingerprints,
        "reason": reason,
    }
