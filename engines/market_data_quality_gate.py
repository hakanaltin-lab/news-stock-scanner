"""AURORA V8.9.5 execution-grade market-data safety gate.

Research/scanner data may be useful without being eligible for order execution.
Execution requires a specifically allowed real-time source and fresh timestamps.
"""

from datetime import datetime, timezone


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
        parsed = parsed.replace(tzinfo=timezone.utc)

    return parsed.astimezone(timezone.utc)


def evaluate_market_data_for_execution(
    market_data,
    now=None,
    max_age_seconds=DEFAULT_EXECUTION_MAX_AGE_SECONDS,
    allowed_sources=None,
):
    market_data = market_data or {}
    allowed_sources = set(allowed_sources or DEFAULT_EXECUTION_SOURCES)
    now_utc = _to_utc_datetime(now) or datetime.now(timezone.utc)

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
    except (TypeError, ValueError):
        price = 0.0

    data_quality = str(
        market_data.get("data_quality") or ""
    ).strip().upper()

    try:
        data_points = int(market_data.get("data_points") or 0)
    except (TypeError, ValueError):
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
        "positive_price": price > 0,
        "data_quality_valid": data_quality not in {
            "",
            "NO_DATA",
            "ERROR",
            "INVALID",
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
