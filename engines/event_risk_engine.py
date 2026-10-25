"""
V7.5 AURORA Earnings & Event Risk Engine

Purpose:
- Detect scheduled company earnings risk
- Detect high-impact US macro event risk
- Use free sources only
- Produce BLOCK / REDUCE_SIZE / ALLOW policy for new entries
- Flag event risk on existing portfolio positions

Sources:
- Yahoo Finance / yfinance for company earnings dates
- Federal Reserve official calendar for FOMC meetings
- U.S. Bureau of Labor Statistics official ICS calendar for CPI,
  Employment Situation and PPI releases

Important:
- Missing event data is reported as UNKNOWN, never silently treated as verified-safe.
- Macro events are a portfolio-wide risk overlay.
- This engine does not send broker orders.
"""

from datetime import datetime, date, timezone
from html import unescape
import re

import requests
import yfinance as yf


FED_CALENDAR_URL = (
    "https://www.federalreserve.gov/newsevents/"
    "{year}-{month_name}.htm"
)

BLS_ICS_URL = (
    "https://www.bls.gov/schedule/news_release/bls.ics"
)

REQUEST_HEADERS = {
    "User-Agent":
    "AURORA-market-research/1.0 contact: research@example.com"
}

REQUEST_TIMEOUT = 12


HIGH_IMPACT_BLS_KEYWORDS = {
    "Consumer Price Index": "CPI",
    "Employment Situation": "EMPLOYMENT",
    "Producer Price Index": "PPI"
}


def safe_int(value, default=None):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def normalize_datetime_to_date(value):
    if value is None:
        return None

    try:
        if hasattr(value, "to_pydatetime"):
            value = value.to_pydatetime()

        if isinstance(value, datetime):
            return value.date()

        if isinstance(value, date):
            return value

        parsed = datetime.fromisoformat(
            str(value).replace("Z", "+00:00")
        )

        return parsed.date()

    except Exception:
        return None


def days_until(event_date, reference_date):
    if not event_date:
        return None

    return (
        event_date - reference_date
    ).days


def get_earnings_policy(days_to_event):
    if days_to_event is None:
        return {
            "risk_level": "UNKNOWN",
            "new_entry_policy": "ALLOW",
            "position_size_multiplier": 1.0,
            "reason": "Earnings date unavailable"
        }

    if days_to_event < 0:
        return {
            "risk_level": "LOW",
            "new_entry_policy": "ALLOW",
            "position_size_multiplier": 1.0,
            "reason": "No upcoming earnings event detected"
        }

    if days_to_event <= 2:
        return {
            "risk_level": "CRITICAL",
            "new_entry_policy": "BLOCK",
            "position_size_multiplier": 0.0,
            "reason":
            "Earnings event is within 2 calendar days"
        }

    if days_to_event <= 5:
        return {
            "risk_level": "HIGH",
            "new_entry_policy": "REDUCE_SIZE",
            "position_size_multiplier": 0.5,
            "reason":
            "Earnings event is within 5 calendar days"
        }

    if days_to_event <= 7:
        return {
            "risk_level": "ELEVATED",
            "new_entry_policy": "REDUCE_SIZE",
            "position_size_multiplier": 0.75,
            "reason":
            "Earnings event is within 7 calendar days"
        }

    return {
        "risk_level": "LOW",
        "new_entry_policy": "ALLOW",
        "position_size_multiplier": 1.0,
        "reason":
        "No near-term earnings restriction"
    }


def fetch_next_earnings_date(
    ticker,
    reference_date=None
):
    reference_date = (
        reference_date
        or
        datetime.now(
            timezone.utc
        ).date()
    )

    candidate_dates = []

    # Preferred source: yfinance earnings calendar history/forecast.
    try:
        earnings_dates = yf.Ticker(
            ticker
        ).get_earnings_dates(
            limit=12
        )

        if (
            earnings_dates is not None
            and
            not earnings_dates.empty
        ):
            for index_value in earnings_dates.index:
                event_date = normalize_datetime_to_date(
                    index_value
                )

                if (
                    event_date
                    and
                    event_date >= reference_date
                ):
                    candidate_dates.append(
                        event_date
                    )

    except Exception:
        pass

    # Fallback: ticker.calendar.
    if not candidate_dates:
        try:
            calendar = yf.Ticker(
                ticker
            ).calendar

            if isinstance(calendar, dict):
                raw_dates = (
                    calendar.get("Earnings Date")
                    or
                    calendar.get("EarningsDate")
                    or
                    []
                )

                if not isinstance(
                    raw_dates,
                    (list, tuple)
                ):
                    raw_dates = [
                        raw_dates
                    ]

                for raw_date in raw_dates:
                    event_date = normalize_datetime_to_date(
                        raw_date
                    )

                    if (
                        event_date
                        and
                        event_date >= reference_date
                    ):
                        candidate_dates.append(
                            event_date
                        )

        except Exception:
            pass

    if not candidate_dates:
        return {
            "ticker": ticker,
            "next_earnings_date": None,
            "days_until_earnings": None,
            "date_status": "UNKNOWN"
        }

    next_date = min(
        candidate_dates
    )

    return {
        "ticker": ticker,
        "next_earnings_date": next_date.isoformat(),
        "days_until_earnings": days_until(
            next_date,
            reference_date
        ),
        "date_status": "AVAILABLE"
    }


def strip_html(html_text):
    text = re.sub(
        r"<script.*?</script>",
        " ",
        html_text,
        flags=re.I | re.S
    )

    text = re.sub(
        r"<style.*?</style>",
        " ",
        text,
        flags=re.I | re.S
    )

    text = re.sub(
        r"<[^>]+>",
        " ",
        text
    )

    text = unescape(
        text
    )

    return re.sub(
        r"\s+",
        " ",
        text
    ).strip()


def fetch_fomc_events(reference_date=None):
    reference_date = (
        reference_date
        or
        datetime.now(
            timezone.utc
        ).date()
    )

    events = []

    month_pairs = []

    year = reference_date.year
    month = reference_date.month

    for offset in range(0, 4):
        absolute_month = (
            month - 1 + offset
        )

        target_year = (
            year
            +
            absolute_month // 12
        )

        target_month = (
            absolute_month % 12
            +
            1
        )

        month_pairs.append(
            (
                target_year,
                target_month
            )
        )

    for target_year, target_month in month_pairs:
        month_name = datetime(
            target_year,
            target_month,
            1
        ).strftime(
            "%B"
        ).lower()

        url = FED_CALENDAR_URL.format(
            year=target_year,
            month_name=month_name
        )

        try:
            response = requests.get(
                url,
                headers=REQUEST_HEADERS,
                timeout=REQUEST_TIMEOUT
            )

            response.raise_for_status()

            text = strip_html(
                response.text
            )

            pattern = re.compile(
                r"FOMC Meeting.*?"
                r"Two-day meeting,\s*"
                r"([A-Za-z]+)\s+"
                r"(\d{1,2})\s*[-–]\s*"
                r"(\d{1,2})",
                flags=re.I
            )

            match = pattern.search(
                text
            )

            if not match:
                continue

            event_month_name = match.group(
                1
            )

            end_day = safe_int(
                match.group(
                    3
                )
            )

            if end_day is None:
                continue

            event_month = datetime.strptime(
                event_month_name,
                "%B"
            ).month

            event_date = date(
                target_year,
                event_month,
                end_day
            )

            if event_date >= reference_date:
                events.append({
                    "event_type": "FOMC",
                    "name": "FOMC Rate Decision",
                    "date": event_date.isoformat(),
                    "source": "Federal Reserve",
                    "source_url": url
                })

        except Exception:
            continue

    unique = {}

    for event in events:
        key = (
            event.get("event_type"),
            event.get("date")
        )
        unique[key] = event

    return sorted(
        unique.values(),
        key=lambda item: item.get(
            "date",
            ""
        )
    )


def unfold_ics_lines(text):
    raw_lines = text.replace(
        "\r\n",
        "\n"
    ).replace(
        "\r",
        "\n"
    ).split(
        "\n"
    )

    lines = []

    for line in raw_lines:
        if (
            line.startswith(" ")
            and
            lines
        ):
            lines[-1] += line[1:]
        else:
            lines.append(
                line
            )

    return lines


def fetch_bls_events(reference_date=None):
    reference_date = (
        reference_date
        or
        datetime.now(
            timezone.utc
        ).date()
    )

    try:
        response = requests.get(
            BLS_ICS_URL,
            headers=REQUEST_HEADERS,
            timeout=REQUEST_TIMEOUT
        )

        response.raise_for_status()

        lines = unfold_ics_lines(
            response.text
        )

    except Exception:
        return []

    events = []
    current = {}

    for line in lines:
        if line == "BEGIN:VEVENT":
            current = {}
            continue

        if line == "END:VEVENT":
            summary = current.get(
                "SUMMARY",
                ""
            )

            raw_date = current.get(
                "DTSTART"
            )

            if not summary or not raw_date:
                current = {}
                continue

            event_type = None

            for keyword, mapped_type in (
                HIGH_IMPACT_BLS_KEYWORDS.items()
            ):
                if keyword.lower() in summary.lower():
                    event_type = mapped_type
                    break

            if not event_type:
                current = {}
                continue

            match = re.search(
                r"(\d{8})",
                raw_date
            )

            if not match:
                current = {}
                continue

            try:
                event_date = datetime.strptime(
                    match.group(
                        1
                    ),
                    "%Y%m%d"
                ).date()
            except Exception:
                current = {}
                continue

            if event_date >= reference_date:
                events.append({
                    "event_type": event_type,
                    "name": summary,
                    "date": event_date.isoformat(),
                    "source": "U.S. Bureau of Labor Statistics",
                    "source_url": BLS_ICS_URL
                })

            current = {}
            continue

        if ":" not in line:
            continue

        key, value = line.split(
            ":",
            1
        )

        key = key.split(
            ";",
            1
        )[0]

        if key in [
            "SUMMARY",
            "DTSTART"
        ]:
            current[key] = value

    return sorted(
        events,
        key=lambda item: item.get(
            "date",
            ""
        )
    )


def get_macro_policy(days_to_event):
    if days_to_event is None:
        return {
            "risk_level": "UNKNOWN",
            "new_entry_policy": "ALLOW",
            "position_size_multiplier": 1.0
        }

    if days_to_event <= 1:
        return {
            "risk_level": "CRITICAL",
            "new_entry_policy": "BLOCK",
            "position_size_multiplier": 0.0
        }

    if days_to_event <= 3:
        return {
            "risk_level": "HIGH",
            "new_entry_policy": "REDUCE_SIZE",
            "position_size_multiplier": 0.5
        }

    if days_to_event <= 7:
        return {
            "risk_level": "ELEVATED",
            "new_entry_policy": "REDUCE_SIZE",
            "position_size_multiplier": 0.75
        }

    return {
        "risk_level": "LOW",
        "new_entry_policy": "ALLOW",
        "position_size_multiplier": 1.0
    }


def analyze_macro_event_risk(
    reference_date=None
):
    reference_date = (
        reference_date
        or
        datetime.now(
            timezone.utc
        ).date()
    )

    fomc_events = fetch_fomc_events(
        reference_date=reference_date
    )

    bls_events = fetch_bls_events(
        reference_date=reference_date
    )

    events = (
        fomc_events
        +
        bls_events
    )

    enriched = []

    for event in events:
        event_date = normalize_datetime_to_date(
            event.get(
                "date"
            )
        )

        days = days_until(
            event_date,
            reference_date
        )

        policy = get_macro_policy(
            days
        )

        enriched.append({
            **event,
            "days_until_event": days,
            "risk_level":
            policy.get(
                "risk_level"
            ),
            "new_entry_policy":
            policy.get(
                "new_entry_policy"
            ),
            "position_size_multiplier":
            policy.get(
                "position_size_multiplier"
            )
        })

    enriched.sort(
        key=lambda item: (
            item.get(
                "days_until_event"
            )
            if item.get(
                "days_until_event"
            ) is not None
            else 99999
        )
    )

    nearest = (
        enriched[0]
        if enriched
        else None
    )

    if nearest:
        overall_policy = {
            "risk_level":
            nearest.get(
                "risk_level",
                "LOW"
            ),
            "new_entry_policy":
            nearest.get(
                "new_entry_policy",
                "ALLOW"
            ),
            "position_size_multiplier":
            nearest.get(
                "position_size_multiplier",
                1.0
            )
        }
    else:
        overall_policy = {
            "risk_level": "UNKNOWN",
            "new_entry_policy": "ALLOW",
            "position_size_multiplier": 1.0
        }

    return {
        "reference_date":
        reference_date.isoformat(),

        "nearest_event":
        nearest,

        "upcoming_events":
        enriched[:12],

        "risk_level":
        overall_policy.get(
            "risk_level"
        ),

        "new_entry_policy":
        overall_policy.get(
            "new_entry_policy"
        ),

        "position_size_multiplier":
        overall_policy.get(
            "position_size_multiplier"
        ),

        "sources": {
            "federal_reserve":
            bool(
                fomc_events
            ),

            "bls":
            bool(
                bls_events
            )
        }
    }


def combine_event_policies(
    earnings_result,
    macro_result
):
    earnings_policy = get_earnings_policy(
        earnings_result.get(
            "days_until_earnings"
        )
    )

    macro_policy = {
        "risk_level":
        macro_result.get(
            "risk_level",
            "UNKNOWN"
        ),

        "new_entry_policy":
        macro_result.get(
            "new_entry_policy",
            "ALLOW"
        ),

        "position_size_multiplier":
        macro_result.get(
            "position_size_multiplier",
            1.0
        )
    }

    policies = [
        (
            "EARNINGS",
            earnings_policy
        ),
        (
            "MACRO",
            macro_policy
        )
    ]

    priority = {
        "ALLOW": 0,
        "REDUCE_SIZE": 1,
        "BLOCK": 2
    }

    dominant_name, dominant_policy = max(
        policies,
        key=lambda item: priority.get(
            item[1].get(
                "new_entry_policy",
                "ALLOW"
            ),
            0
        )
    )

    size_multiplier = min(
        safe_float(
            earnings_policy.get(
                "position_size_multiplier",
                1.0
            ),
            1.0
        ),
        safe_float(
            macro_policy.get(
                "position_size_multiplier",
                1.0
            ),
            1.0
        )
    )

    reasons = []

    if earnings_policy.get(
        "new_entry_policy"
    ) != "ALLOW":
        reasons.append(
            earnings_policy.get(
                "reason"
            )
        )

    nearest_macro = macro_result.get(
        "nearest_event"
    )

    if (
        nearest_macro
        and
        macro_policy.get(
            "new_entry_policy"
        )
        !=
        "ALLOW"
    ):
        reasons.append(
            (
                f"{nearest_macro.get('event_type')} "
                f"in {nearest_macro.get('days_until_event')} "
                "calendar days"
            )
        )

    if not reasons:
        reasons.append(
            "No scheduled event restriction"
        )

    return {
        "risk_level":
        dominant_policy.get(
            "risk_level",
            "LOW"
        ),

        "dominant_risk_source":
        dominant_name,

        "new_entry_policy":
        dominant_policy.get(
            "new_entry_policy",
            "ALLOW"
        ),

        "position_size_multiplier":
        round(
            size_multiplier,
            2
        ),

        "reasons":
        reasons
    }


def analyze_ticker_event_risk(
    ticker,
    macro_result=None,
    reference_date=None
):
    reference_date = (
        reference_date
        or
        datetime.now(
            timezone.utc
        ).date()
    )

    macro_result = (
        macro_result
        or
        analyze_macro_event_risk(
            reference_date=reference_date
        )
    )

    earnings_result = (
        fetch_next_earnings_date(
            ticker,
            reference_date=reference_date
        )
    )

    combined = combine_event_policies(
        earnings_result,
        macro_result
    )

    return {
        "ticker":
        ticker,

        "earnings":
        earnings_result,

        "macro":
        {
            "risk_level":
            macro_result.get(
                "risk_level"
            ),

            "nearest_event":
            macro_result.get(
                "nearest_event"
            )
        },

        "combined":
        combined
    }


def build_event_risk_summary(
    portfolio_results,
    opportunity_analysis
):
    reference_date = datetime.now(
        timezone.utc
    ).date()

    macro_result = (
        analyze_macro_event_risk(
            reference_date=reference_date
        )
    )

    tickers = []

    for item in portfolio_results:
        ticker = item.get(
            "ticker"
        )

        if (
            ticker
            and
            ticker not in tickers
        ):
            tickers.append(
                ticker
            )

    for item in (
        opportunity_analysis.get(
            "top_actionable",
            []
        )
        or
        []
    ):
        ticker = item.get(
            "ticker"
        )

        if (
            ticker
            and
            ticker not in tickers
        ):
            tickers.append(
                ticker
            )

    ticker_risks = {}

    for ticker in tickers:
        try:
            ticker_risks[
                ticker
            ] = analyze_ticker_event_risk(
                ticker,
                macro_result=macro_result,
                reference_date=reference_date
            )

        except Exception as error:
            ticker_risks[
                ticker
            ] = {
                "ticker": ticker,
                "earnings": {
                    "next_earnings_date": None,
                    "days_until_earnings": None,
                    "date_status": "ERROR"
                },
                "macro": {
                    "risk_level":
                    macro_result.get(
                        "risk_level"
                    ),
                    "nearest_event":
                    macro_result.get(
                        "nearest_event"
                    )
                },
                "combined": {
                    "risk_level": "UNKNOWN",
                    "dominant_risk_source": "ERROR",
                    "new_entry_policy": "ALLOW",
                    "position_size_multiplier": 1.0,
                    "reasons": [
                        str(error)
                    ]
                }
            }

    portfolio_alerts = []

    for item in portfolio_results:
        ticker = item.get(
            "ticker"
        )

        risk = ticker_risks.get(
            ticker,
            {}
        )

        combined = risk.get(
            "combined",
            {}
        )

        if combined.get(
            "new_entry_policy"
        ) in [
            "BLOCK",
            "REDUCE_SIZE"
        ]:
            portfolio_alerts.append({
                "ticker":
                ticker,

                "risk_level":
                combined.get(
                    "risk_level"
                ),

                "event_policy":
                combined.get(
                    "new_entry_policy"
                ),

                "earnings":
                risk.get(
                    "earnings"
                ),

                "macro":
                risk.get(
                    "macro"
                ),

                "reasons":
                combined.get(
                    "reasons",
                    []
                )
            })

    actionable_alerts = []

    for item in (
        opportunity_analysis.get(
            "top_actionable",
            []
        )
        or
        []
    ):
        ticker = item.get(
            "ticker"
        )

        risk = ticker_risks.get(
            ticker,
            {}
        )

        combined = risk.get(
            "combined",
            {}
        )

        if combined.get(
            "new_entry_policy"
        ) in [
            "BLOCK",
            "REDUCE_SIZE"
        ]:
            actionable_alerts.append({
                "ticker":
                ticker,

                "base_action":
                item.get(
                    "action"
                ),

                "risk_level":
                combined.get(
                    "risk_level"
                ),

                "event_policy":
                combined.get(
                    "new_entry_policy"
                ),

                "size_multiplier":
                combined.get(
                    "position_size_multiplier",
                    1.0
                ),

                "earnings":
                risk.get(
                    "earnings"
                ),

                "macro":
                risk.get(
                    "macro"
                ),

                "reasons":
                combined.get(
                    "reasons",
                    []
                )
            })

    return {
        "engine":
        "V7.5 Earnings & Event Risk Engine",

        "generated":
        datetime.now(
            timezone.utc
        ).isoformat(),

        "reference_date":
        reference_date.isoformat(),

        "macro_event_risk":
        macro_result,

        "ticker_risk":
        ticker_risks,

        "portfolio_alert_count":
        len(
            portfolio_alerts
        ),

        "portfolio_alerts":
        portfolio_alerts,

        "actionable_alert_count":
        len(
            actionable_alerts
        ),

        "actionable_alerts":
        actionable_alerts,

        "data_quality":
        "MIXED_OFFICIAL_AND_MARKET_CALENDAR"
    }
