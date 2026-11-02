"""Offline G6.22 freshness diagnostic; NEVER authorizes trading.

Timestamp age is a necessary but insufficient condition. Operator provenance,
Gateway Read-Only API configuration and broker identity still require separate
independent review. No network or broker calls.
"""
from datetime import datetime, timezone, timedelta

MAX_AGE_SECONDS = 300
MAX_FUTURE_SKEW_SECONDS = 30


def evaluate_freshness(report, now=None):
    base = {
        "status": "BLOCKED",
        "paper_order_submission_allowed": False,
        "live_trading_allowed": False,
        "release_approved": False,
        "broker_session_independently_verified": False,
    }
    if not isinstance(report, dict):
        return {**base, "reason": "INVALID_REPORT"}
    value = report.get("snapshot_generated_at_utc")
    if not isinstance(value, str) or not value:
        return {**base, "reason": "MISSING_TIMESTAMP"}
    try:
        timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return {**base, "reason": "INVALID_TIMESTAMP"}
    if timestamp.tzinfo is None or timestamp.utcoffset() != timedelta(0):
        return {**base, "reason": "NON_UTC_TIMESTAMP"}
    if now is None:
        now = datetime.now(timezone.utc)
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() != timedelta(0):
        return {**base, "reason": "INVALID_CLOCK"}
    age = (now - timestamp).total_seconds()
    if age < -MAX_FUTURE_SKEW_SECONDS:
        return {**base, "reason": "FUTURE_TIMESTAMP"}
    if age > MAX_AGE_SECONDS:
        return {**base, "reason": "STALE_TIMESTAMP"}
    return {
        **base,
        "status": "FRESHNESS_DIAGNOSTIC_PASSED",
        "reason": "FRESHNESS_ONLY_NOT_AUTHENTICITY_OR_RELEASE_APPROVAL",
    }
