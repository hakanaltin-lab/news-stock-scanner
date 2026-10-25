"""
V8.5 AURORA Fundamental Thesis & Valuation Engine

Purpose:
- Build a current fundamental thesis snapshot for portfolio holdings
- Separate business-thesis health from market-price weakness
- Use growth, profitability, cash flow, balance sheet, valuation and
  estimate-revision evidence
- Cache current fundamental snapshots once per UTC day to limit provider load
- Provide a thesis-confirmation review for REDUCE / EXIT signals
- Do NOT change live portfolio actions in V8.5

Data source:
- Yahoo Finance / yfinance current company fundamentals and analyst fields

Important:
- This is a current snapshot, not point-in-time historical fundamentals.
- Missing fields remain neutral rather than being invented.
- No broker orders are sent.
"""

from datetime import datetime, timezone
import json
import os

import yfinance as yf


ENGINE_VERSION = (
    "V8.5 Fundamental Thesis & Valuation Engine"
)

FUNDAMENTAL_SIGNATURE = "V8.5.1"

CACHE_FILE = (
    "docs/fundamental_thesis_cache.json"
)


def safe_float(
    value,
    default=None
):
    try:
        if value is None:
            return default

        return float(
            value
        )

    except (
        TypeError,
        ValueError
    ):
        return default


def clamp(
    value,
    low=0.0,
    high=100.0
):
    return max(
        low,
        min(
            high,
            value
        )
    )


def pct_value(
    value
):
    value = safe_float(
        value,
        None
    )

    if value is None:
        return None

    if abs(
        value
    ) <= 3:
        return (
            value
            *
            100
        )

    return value


def score_growth(
    revenue_growth,
    earnings_growth
):
    values = []

    if revenue_growth is not None:
        values.append(
            clamp(
                50
                +
                revenue_growth
                *
                1.4
            )
        )

    if earnings_growth is not None:
        values.append(
            clamp(
                50
                +
                earnings_growth
                *
                1.0
            )
        )

    if not values:
        return None

    return round(
        sum(
            values
        )
        /
        len(
            values
        ),
        1
    )


def score_profitability(
    operating_margin,
    profit_margin,
    return_on_equity
):
    values = []

    if operating_margin is not None:
        values.append(
            clamp(
                40
                +
                operating_margin
                *
                1.5
            )
        )

    if profit_margin is not None:
        values.append(
            clamp(
                40
                +
                profit_margin
                *
                1.4
            )
        )

    if return_on_equity is not None:
        values.append(
            clamp(
                40
                +
                return_on_equity
                *
                1.2
            )
        )

    if not values:
        return None

    return round(
        sum(
            values
        )
        /
        len(
            values
        ),
        1
    )


def score_cash_flow(
    free_cash_flow,
    operating_cash_flow,
    market_cap
):
    values = []

    if free_cash_flow is not None:
        values.append(
            75.0
            if free_cash_flow > 0
            else
            20.0
        )

    if operating_cash_flow is not None:
        values.append(
            75.0
            if operating_cash_flow > 0
            else
            20.0
        )

    if (
        free_cash_flow is not None
        and
        market_cap is not None
        and
        market_cap > 0
    ):
        fcf_yield = (
            free_cash_flow
            /
            market_cap
            *
            100
        )

        values.append(
            clamp(
                35
                +
                fcf_yield
                *
                8
            )
        )

    if not values:
        return None

    return round(
        sum(
            values
        )
        /
        len(
            values
        ),
        1
    )


def score_balance_sheet(
    total_cash,
    total_debt,
    debt_to_equity,
    current_ratio
):
    values = []

    if (
        total_cash is not None
        and
        total_debt is not None
    ):
        if total_cash >= total_debt:
            values.append(
                85.0
            )

        elif total_debt > 0:
            cash_debt_ratio = (
                total_cash
                /
                total_debt
            )

            values.append(
                clamp(
                    35
                    +
                    cash_debt_ratio
                    *
                    45
                )
            )

    if debt_to_equity is not None:
        if debt_to_equity <= 50:
            values.append(
                85.0
            )

        elif debt_to_equity <= 100:
            values.append(
                70.0
            )

        elif debt_to_equity <= 200:
            values.append(
                50.0
            )

        else:
            values.append(
                25.0
            )

    if current_ratio is not None:
        if current_ratio >= 1.5:
            values.append(
                80.0
            )

        elif current_ratio >= 1.0:
            values.append(
                60.0
            )

        else:
            values.append(
                30.0
            )

    if not values:
        return None

    return round(
        sum(
            values
        )
        /
        len(
            values
        ),
        1
    )


def score_valuation(
    forward_pe,
    peg_ratio,
    fcf_yield
):
    values = []

    if forward_pe is not None:
        if forward_pe <= 0:
            values.append(
                20.0
            )

        elif forward_pe <= 12:
            values.append(
                90.0
            )

        elif forward_pe <= 20:
            values.append(
                75.0
            )

        elif forward_pe <= 30:
            values.append(
                60.0
            )

        elif forward_pe <= 45:
            values.append(
                45.0
            )

        else:
            values.append(
                30.0
            )

    if peg_ratio is not None:
        if peg_ratio <= 0:
            values.append(
                25.0
            )

        elif peg_ratio <= 1:
            values.append(
                85.0
            )

        elif peg_ratio <= 1.5:
            values.append(
                70.0
            )

        elif peg_ratio <= 2.5:
            values.append(
                50.0
            )

        else:
            values.append(
                30.0
            )

    if fcf_yield is not None:
        values.append(
            clamp(
                35
                +
                fcf_yield
                *
                8
            )
        )

    if not values:
        return None

    return round(
        sum(
            values
        )
        /
        len(
            values
        ),
        1
    )


def revision_counts(
    stock
):
    result = {
        "up_7d":
        0,

        "up_30d":
        0,

        "down_7d":
        0,

        "down_30d":
        0,

        "available":
        False
    }

    try:
        revisions = (
            stock.eps_revisions
        )

        if (
            revisions is None
            or
            revisions.empty
        ):
            return result

        columns = {
            str(
                column
            ).lower():
            column
            for column in revisions.columns
        }

        def total(
            fragment
        ):
            for lowered, original in (
                columns.items()
            ):
                if fragment in lowered:
                    series = (
                        revisions[
                            original
                        ]
                        .dropna()
                    )

                    if series.empty:
                        return 0

                    return int(
                        series.sum()
                    )

            return 0

        result = {
            "up_7d":
            total(
                "uplast7"
            ),

            "up_30d":
            total(
                "uplast30"
            ),

            "down_7d":
            total(
                "downlast7"
            ),

            "down_30d":
            total(
                "downlast30"
            ),

            "available":
            True
        }

    except Exception:
        pass

    return result


def score_revisions(
    revision_data,
    analyst_upside_pct,
    recommendation_mean
):
    values = []

    if revision_data.get(
        "available"
    ):
        positive = (
            revision_data.get(
                "up_7d",
                0
            )
            +
            revision_data.get(
                "up_30d",
                0
            )
        )

        negative = (
            revision_data.get(
                "down_7d",
                0
            )
            +
            revision_data.get(
                "down_30d",
                0
            )
        )

        total = (
            positive
            +
            negative
        )

        if total > 0:
            values.append(
                clamp(
                    50
                    +
                    (
                        positive
                        -
                        negative
                    )
                    /
                    total
                    *
                    40
                )
            )

        else:
            values.append(
                50.0
            )

    if analyst_upside_pct is not None:
        values.append(
            clamp(
                50
                +
                analyst_upside_pct
                *
                1.2
            )
        )

    if recommendation_mean is not None:
        # Yahoo convention is typically 1=Strong Buy, 5=Sell.
        values.append(
            clamp(
                100
                -
                (
                    recommendation_mean
                    -
                    1
                )
                *
                25
            )
        )

    if not values:
        return None

    return round(
        sum(
            values
        )
        /
        len(
            values
        ),
        1
    )


def classify_thesis(
    thesis_score,
    hard_break_count,
    coverage_ratio
):
    if coverage_ratio < 0.35:
        return "INSUFFICIENT_DATA"

    if hard_break_count >= 2:
        return "BROKEN"

    if hard_break_count == 1:
        return "DETERIORATING"

    if thesis_score >= 75:
        return "STRONG"

    if thesis_score >= 60:
        return "HEALTHY"

    if thesis_score >= 45:
        return "MIXED"

    if thesis_score >= 30:
        return "DETERIORATING"

    return "BROKEN"


def load_cache():
    if not os.path.exists(
        CACHE_FILE
    ):
        return {
            "signature":
            FUNDAMENTAL_SIGNATURE,

            "date":
            None,

            "snapshots":
            {}
        }

    try:
        with open(
            CACHE_FILE,
            "r",
            encoding="utf-8"
        ) as file:
            data = json.load(
                file
            )

        if not isinstance(
            data,
            dict
        ):
            raise ValueError(
                "Invalid cache"
            )

        if (
            data.get(
                "signature"
            )
            !=
            FUNDAMENTAL_SIGNATURE
        ):
            return {
                "signature":
                FUNDAMENTAL_SIGNATURE,

                "date":
                None,

                "snapshots":
                {}
            }

        if not isinstance(
            data.get(
                "snapshots"
            ),
            dict
        ):
            data[
                "snapshots"
            ] = {}

        return data

    except Exception:
        return {
            "signature":
            FUNDAMENTAL_SIGNATURE,

            "date":
            None,

            "snapshots":
            {}
        }


def save_cache(
    data
):
    os.makedirs(
        os.path.dirname(
            CACHE_FILE
        ),
        exist_ok=True
    )

    with open(
        CACHE_FILE,
        "w",
        encoding="utf-8"
    ) as file:
        json.dump(
            data,
            file,
            indent=2,
            ensure_ascii=False
        )


def analyze_fundamental_thesis(
    ticker,
    current_price=None,
    force=False
):
    ticker = str(
        ticker
    ).strip().upper()

    today = (
        datetime.now(
            timezone.utc
        ).date().isoformat()
    )

    cache = load_cache()

    if (
        not force
        and
        cache.get(
            "date"
        )
        ==
        today
        and
        ticker
        in
        (
            cache.get(
                "snapshots",
                {}
            )
            or
            {}
        )
    ):
        snapshot = (
            cache[
                "snapshots"
            ][
                ticker
            ]
        )

        snapshot[
            "cache_status"
        ] = "REUSED"

        return snapshot

    stock = yf.Ticker(
        ticker
    )

    try:
        info = (
            stock.get_info()
            or
            {}
        )

    except Exception:
        try:
            info = (
                stock.info
                or
                {}
            )

        except Exception:
            info = {}

    price = safe_float(
        current_price,
        None
    )

    if price is None:
        price = safe_float(
            info.get(
                "currentPrice"
            ),
            None
        )

    revenue_growth = pct_value(
        info.get(
            "revenueGrowth"
        )
    )

    earnings_growth = pct_value(
        info.get(
            "earningsGrowth"
        )
    )

    operating_margin = pct_value(
        info.get(
            "operatingMargins"
        )
    )

    profit_margin = pct_value(
        info.get(
            "profitMargins"
        )
    )

    return_on_equity = pct_value(
        info.get(
            "returnOnEquity"
        )
    )

    free_cash_flow = safe_float(
        info.get(
            "freeCashflow"
        ),
        None
    )

    operating_cash_flow = safe_float(
        info.get(
            "operatingCashflow"
        ),
        None
    )

    market_cap = safe_float(
        info.get(
            "marketCap"
        ),
        None
    )

    total_cash = safe_float(
        info.get(
            "totalCash"
        ),
        None
    )

    total_debt = safe_float(
        info.get(
            "totalDebt"
        ),
        None
    )

    debt_to_equity = safe_float(
        info.get(
            "debtToEquity"
        ),
        None
    )

    current_ratio = safe_float(
        info.get(
            "currentRatio"
        ),
        None
    )

    forward_pe = safe_float(
        info.get(
            "forwardPE"
        ),
        None
    )

    peg_ratio = safe_float(
        info.get(
            "pegRatio"
        ),
        None
    )

    target_mean_price = safe_float(
        info.get(
            "targetMeanPrice"
        ),
        None
    )

    recommendation_mean = safe_float(
        info.get(
            "recommendationMean"
        ),
        None
    )

    analyst_count = safe_float(
        info.get(
            "numberOfAnalystOpinions"
        ),
        None
    )

    analyst_upside_pct = None

    if (
        target_mean_price is not None
        and
        price is not None
        and
        price > 0
    ):
        analyst_upside_pct = (
            target_mean_price
            /
            price
            -
            1
        ) * 100

    fcf_yield = None

    if (
        free_cash_flow is not None
        and
        market_cap is not None
        and
        market_cap > 0
    ):
        fcf_yield = (
            free_cash_flow
            /
            market_cap
            *
            100
        )

    revisions = revision_counts(
        stock
    )

    component_scores = {
        "growth":
        score_growth(
            revenue_growth,
            earnings_growth
        ),

        "profitability":
        score_profitability(
            operating_margin,
            profit_margin,
            return_on_equity
        ),

        "cash_flow":
        score_cash_flow(
            free_cash_flow,
            operating_cash_flow,
            market_cap
        ),

        "balance_sheet":
        score_balance_sheet(
            total_cash,
            total_debt,
            debt_to_equity,
            current_ratio
        ),

        "valuation":
        score_valuation(
            forward_pe,
            peg_ratio,
            fcf_yield
        ),

        "revisions":
        score_revisions(
            revisions,
            analyst_upside_pct,
            recommendation_mean
        )
    }

    weights = {
        "growth": 0.20,
        "profitability": 0.20,
        "cash_flow": 0.20,
        "balance_sheet": 0.15,
        "valuation": 0.10,
        "revisions": 0.15
    }

    available_weight = 0.0

    weighted_score = 0.0

    for name, weight in (
        weights.items()
    ):
        value = component_scores.get(
            name
        )

        if value is None:
            continue

        available_weight += (
            weight
        )

        weighted_score += (
            value
            *
            weight
        )

    thesis_score = (
        weighted_score
        /
        available_weight
        if available_weight > 0
        else 50.0
    )

    coverage_ratio = (
        available_weight
        /
        sum(
            weights.values()
        )
    )

    hard_breaks = []

    if (
        revenue_growth is not None
        and
        revenue_growth < -10
    ):
        hard_breaks.append(
            "Revenue growth below -10%"
        )

    if (
        earnings_growth is not None
        and
        earnings_growth < -20
    ):
        hard_breaks.append(
            "Earnings growth below -20%"
        )

    if (
        free_cash_flow is not None
        and
        operating_cash_flow is not None
        and
        free_cash_flow < 0
        and
        operating_cash_flow < 0
    ):
        hard_breaks.append(
            "Free cash flow and operating cash flow both negative"
        )

    if (
        debt_to_equity is not None
        and
        current_ratio is not None
        and
        debt_to_equity > 250
        and
        current_ratio < 1
    ):
        hard_breaks.append(
            "High leverage with sub-1 current ratio"
        )

    revision_negative = (
        revisions.get(
            "down_30d",
            0
        )
        >
        revisions.get(
            "up_30d",
            0
        )
        +
        2
    )

    if revision_negative:
        hard_breaks.append(
            "EPS revisions materially skew negative"
        )

    thesis_health = classify_thesis(
        thesis_score,
        len(
            hard_breaks
        ),
        coverage_ratio
    )

    if coverage_ratio >= 0.75:
        data_quality = "GOOD"

    elif coverage_ratio >= 0.45:
        data_quality = "PARTIAL"

    else:
        data_quality = "INSUFFICIENT"

    snapshot = {
        "engine":
        ENGINE_VERSION,

        "fundamental_signature":
        FUNDAMENTAL_SIGNATURE,

        "timestamp":
        datetime.now(
            timezone.utc
        ).isoformat(),

        "ticker":
        ticker,

        "cache_status":
        "FRESH",

        "data_source":
        "YAHOO_FINANCE_CURRENT_SNAPSHOT",

        "point_in_time_historical":
        False,

        "data_quality":
        data_quality,

        "coverage_ratio":
        round(
            coverage_ratio,
            3
        ),

        "thesis_score":
        round(
            thesis_score,
            1
        ),

        "thesis_health":
        thesis_health,

        "hard_break_count":
        len(
            hard_breaks
        ),

        "hard_breaks":
        hard_breaks,

        "component_scores":
        component_scores,

        "fundamentals": {
            "revenue_growth_pct":
            (
                round(
                    revenue_growth,
                    2
                )
                if revenue_growth is not None
                else None
            ),

            "earnings_growth_pct":
            (
                round(
                    earnings_growth,
                    2
                )
                if earnings_growth is not None
                else None
            ),

            "operating_margin_pct":
            (
                round(
                    operating_margin,
                    2
                )
                if operating_margin is not None
                else None
            ),

            "profit_margin_pct":
            (
                round(
                    profit_margin,
                    2
                )
                if profit_margin is not None
                else None
            ),

            "return_on_equity_pct":
            (
                round(
                    return_on_equity,
                    2
                )
                if return_on_equity is not None
                else None
            ),

            "free_cash_flow":
            free_cash_flow,

            "operating_cash_flow":
            operating_cash_flow,

            "fcf_yield_pct":
            (
                round(
                    fcf_yield,
                    2
                )
                if fcf_yield is not None
                else None
            ),

            "total_cash":
            total_cash,

            "total_debt":
            total_debt,

            "debt_to_equity":
            debt_to_equity,

            "current_ratio":
            current_ratio
        },

        "valuation": {
            "forward_pe":
            forward_pe,

            "peg_ratio":
            peg_ratio
        },

        "analyst_revision_context": {
            "target_mean_price":
            target_mean_price,

            "analyst_upside_pct":
            (
                round(
                    analyst_upside_pct,
                    2
                )
                if analyst_upside_pct is not None
                else None
            ),

            "recommendation_mean":
            recommendation_mean,

            "analyst_count":
            analyst_count,

            "eps_revisions":
            revisions
        },

        "interpretation":
        (
            "Current thesis-health evidence only. Use as a confirmation "
            "layer for price-driven risk signals, not as standalone proof."
        )
    }

    if cache.get(
        "date"
    ) != today:
        cache = {
            "signature":
            FUNDAMENTAL_SIGNATURE,

            "date":
            today,

            "snapshots":
            {}
        }

    cache.setdefault(
        "snapshots",
        {}
    )[
        ticker
    ] = snapshot

    save_cache(
        cache
    )

    return snapshot


def review_price_action_with_thesis(
    base_action,
    thesis_result
):
    base_action = (
        base_action
        or
        "WATCH"
    ).upper()

    thesis_result = (
        thesis_result
        or
        {}
    )

    thesis_health = (
        thesis_result.get(
            "thesis_health"
        )
        or
        "INSUFFICIENT_DATA"
    )

    data_quality = (
        thesis_result.get(
            "data_quality"
        )
        or
        "INSUFFICIENT"
    )

    if base_action not in {
        "REDUCE",
        "EXIT"
    }:
        return {
            "base_action":
            base_action,

            "review_status":
            "NOT_APPLICABLE",

            "thesis_shadow_action":
            base_action,

            "live_action_changed":
            False,

            "reason":
            (
                "Fundamental confirmation is only required for price-driven "
                "REDUCE / EXIT signals in V8.5."
            )
        }

    if data_quality == "INSUFFICIENT":
        return {
            "base_action":
            base_action,

            "review_status":
            "INSUFFICIENT_DATA",

            "thesis_shadow_action":
            "WATCH",

            "live_action_changed":
            False,

            "reason":
            (
                "Price-driven sell signal is not fundamentally confirmed "
                "because thesis data coverage is insufficient."
            )
        }

    if thesis_health == "BROKEN":
        return {
            "base_action":
            base_action,

            "review_status":
            "CONFIRMED",

            "thesis_shadow_action":
            "EXIT",

            "live_action_changed":
            False,

            "reason":
            (
                "Business thesis is broken; price weakness is fundamentally "
                "confirmed."
            )
        }

    if thesis_health == "DETERIORATING":
        return {
            "base_action":
            base_action,

            "review_status":
            "CONFIRMED_PARTIAL",

            "thesis_shadow_action":
            "REDUCE",

            "live_action_changed":
            False,

            "reason":
            (
                "Business thesis is deteriorating; a partial reduction is "
                "fundamentally supported."
            )
        }

    if thesis_health == "MIXED":
        return {
            "base_action":
            base_action,

            "review_status":
            "NOT_CONFIRMED",

            "thesis_shadow_action":
            "WATCH",

            "live_action_changed":
            False,

            "reason":
            (
                "Fundamental evidence is mixed; price weakness alone should "
                "not be treated as a confirmed sell thesis."
            )
        }

    return {
        "base_action":
        base_action,

        "review_status":
        "CONTRADICTED",

        "thesis_shadow_action":
        "HOLD",

        "live_action_changed":
        False,

        "reason":
        (
            "Fundamental thesis remains healthy/strong and contradicts the "
            "price-only sell signal."
        )
    }
