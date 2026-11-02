"""AURORA V8.9.5 execution-grade market-data safety gate.

Research/scanner data may be useful without being eligible for order execution.
Execution requires a specifically allowed real-time source and fresh timestamps.
"""

from datetime import datetime, timezone
import math


DEFAULT_EXECUTION_MAX_AGE_SECONDS = 10
DEFAULT_EXECUTION_SOURCES = {"IBKR_REALTIME"}


def _to_utc_datetime(value):
    if value is None:
        return None

    if isinstance(value, datetime):
        parsed = value
    else:
        text = str(value).strip()
        if not text:
            return None
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            return None

    if parsed.tzinfo is None:
        return None  # Ambiguous timestamps must never authorize an order.

    return parsed.astimezone(timezone.utc)


def evaluate_market_data_for_execution(
    market_data,
    now=None,
    max_age_seconds=DEFAULT_EXECUTION_MAX_AGE_SECONDS,
    allowed_sources=None,
):
    if not isinstance(market_data, dict):
        market_data = {}
    allowed_sources = set(DEFAULT_EXECUTION_SOURCES)
    # Caller-supplied allowlists must not expand the execution trust boundary.
    now_utc = datetime.now(timezone.utc) if now is None else _to_utc_datetime(now)
    if now_utc is None:
        return {
            "execution_eligible": False,
            "decision": "BLOCK",
            "failure_reasons": ["INVALID_REFERENCE_CLOCK"],
            "checks": {"reference_clock_valid": False},
        }

    source = str(market_data.get("source") or "").strip().upper()
    timestamp = _to_utc_datetime(
        market_data.get("market_timestamp")
        or market_data.get("timestamp")
    )

    try:
        price = float(
            market_data.get("last_price")
            if market_data.get("last_price") is not None
            else 0
        )
    except (TypeError, ValueError, OverflowError):
        price = 0.0

    data_quality = str(
        market_data.get("data_quality") or ""
    ).strip().upper()

    try:
        raw_points = market_data.get("data_points")
        data_points = int(raw_points) if not isinstance(raw_points, bool) else 0
        if data_points <= 0 or str(raw_points).strip() != str(data_points):
            data_points = 0
    except (TypeError, ValueError, OverflowError):
        data_points = 0

    age_seconds = None
    future_skew_seconds = None
    if timestamp is not None:
        raw_age_seconds = (now_utc - timestamp).total_seconds()
        age_seconds = max(0.0, raw_age_seconds)
        future_skew_seconds = max(0.0, -raw_age_seconds)

    checks = {
        "source_allowed": source in allowed_sources,
        "timestamp_available": timestamp is not None,
        "fresh": (
            age_seconds is not None
            and age_seconds <= float(max_age_seconds)
        ),
        "clock_sane": (
            future_skew_seconds is not None
            and future_skew_seconds <= 2.0
        ),
        "positive_price": math.isfinite(price) and price > 0,
        "explicit_execution_eligibility": market_data.get("execution_eligible") is True,
        "broker_timestamp_verified": (
            market_data.get("broker_market_timestamp_verified") is True
        ),
        "data_quality_valid": data_quality not in {
            "",
            "NO_DATA",
            "ERROR",
            "INVALID",
            "UNVERIFIED",
        },
        "has_data_points": data_points > 0,
    }

    failures = [
        name
        for name, passed in checks.items()
        if not passed
    ]

    return {
        "execution_eligible": not failures,
        "source": source or None,
        "market_timestamp": (
            timestamp.isoformat()
            if timestamp is not None
            else None
        ),
        "data_age_seconds": (
            round(age_seconds, 3)
            if age_seconds is not None
            else None
        ),
        "future_skew_seconds": (
            round(future_skew_seconds, 3)
            if future_skew_seconds is not None
            else None
        ),
        "max_age_seconds": float(max_age_seconds),
        "checks": checks,
        "failure_reasons": failures,
        "decision": (
            "PASS"
            if not failures
            else "BLOCK"
        ),
    }
