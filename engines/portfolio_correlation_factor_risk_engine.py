"""
V7.6 AURORA Portfolio Correlation & Factor Risk Engine

Purpose:
- Measure hidden portfolio concentration using actual return correlations
- Detect high-correlation clusters across final projected holdings
- Measure portfolio sensitivity to broad market / growth / semiconductor / energy factors
- Combine correlation, cluster, factor and theme concentration into one hidden-risk score

Method:
- Uses up to ~8 months of daily adjusted market history
- Uses the V7.3/V7.5 final projected portfolio weights
- Excludes CASH from security correlation calculations
- Keeps CASH as a zero-return allocation when calculating portfolio factor sensitivity

Factor proxies:
- SPY = broad US equity market
- QQQ = growth / mega-cap technology
- SMH = semiconductor complex
- XLE = energy

Important:
- Diagnostic/risk-governance layer only.
- This version does not automatically sell positions.
- No broker orders are sent.
"""

from datetime import datetime, timezone
from functools import lru_cache
import math

import numpy as np
import pandas as pd
import yfinance as yf


MIN_OBSERVATIONS = 40
HIGH_CORRELATION_THRESHOLD = 0.75
VERY_HIGH_CORRELATION_THRESHOLD = 0.85
MAX_CLUSTER_EXPOSURE_LIMIT_PCT = 60.0
THEME_CONCENTRATION_LIMIT_PCT = 35.0


FACTOR_PROXIES = {
    "MARKET": "SPY",
    "GROWTH_TECH": "QQQ",
    "SEMICONDUCTOR": "SMH",
    "ENERGY": "XLE"
}


def safe_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


@lru_cache(maxsize=128)
def fetch_daily_returns(ticker):
    try:
        history = yf.Ticker(
            ticker
        ).history(
            period="8mo",
            interval="1d",
            auto_adjust=True
        )

        if history is None or history.empty:
            return None

        close = history.get(
            "Close"
        )

        if close is None:
            return None

        returns = (
            close
            .dropna()
            .pct_change()
            .dropna()
        )

        if len(returns) < MIN_OBSERVATIONS:
            return None

        returns.name = ticker

        return returns

    except Exception:
        return None


def build_returns_frame(tickers):
    series_list = []

    missing = []

    for ticker in tickers:
        returns = fetch_daily_returns(
            ticker
        )

        if returns is None:
            missing.append(
                ticker
            )
            continue

        series_list.append(
            returns
        )

    if not series_list:
        return (
            pd.DataFrame(),
            missing
        )

    frame = pd.concat(
        series_list,
        axis=1,
        join="outer"
    ).sort_index()

    return (
        frame,
        missing
    )


def get_final_security_positions(
    final_portfolio_projection
):
    positions = []

    for item in (
        final_portfolio_projection.get(
            "final_positions",
            []
        )
        or
        []
    ):
        ticker = item.get(
            "ticker"
        )

        source = item.get(
            "source"
        )

        final_value = safe_float(
            item.get(
                "final_value",
                0
            )
        )

        weight = safe_float(
            item.get(
                "final_weight_pct",
                0
            )
        )

        if (
            not ticker
            or
            ticker == "CASH"
            or
            source == "CASH"
            or
            final_value <= 0
            or
            weight <= 0
        ):
            continue

        positions.append({
            "ticker":
            ticker,

            "sector":
            item.get(
                "sector",
                "Unknown"
            ),

            "theme":
            item.get(
                "theme",
                "Unknown"
            ),

            "final_value":
            round(
                final_value,
                2
            ),

            "final_weight_pct":
            round(
                weight,
                2
            )
        })

    return positions


def normalize_invested_weights(
    positions
):
    total = sum(
        safe_float(
            item.get(
                "final_weight_pct",
                0
            )
        )
        for item in positions
    )

    if total <= 0:
        return {}

    return {
        item.get("ticker"):
        safe_float(
            item.get(
                "final_weight_pct",
                0
            )
        )
        /
        total
        for item in positions
        if item.get("ticker")
    }


def calculate_pairwise_analysis(
    positions,
    returns_frame
):
    tickers = [
        item.get(
            "ticker"
        )
        for item in positions
        if item.get(
            "ticker"
        )
        in returns_frame.columns
    ]

    invested_weights = (
        normalize_invested_weights(
            positions
        )
    )

    pairs = []

    weighted_corr_sum = 0.0
    pair_weight_sum = 0.0

    for index, ticker_a in enumerate(
        tickers
    ):
        for ticker_b in tickers[
            index + 1:
        ]:
            aligned = returns_frame[
                [
                    ticker_a,
                    ticker_b
                ]
            ].dropna()

            if len(
                aligned
            ) < MIN_OBSERVATIONS:
                continue

            correlation = aligned[
                ticker_a
            ].corr(
                aligned[
                    ticker_b
                ]
            )

            if pd.isna(
                correlation
            ):
                continue

            correlation = float(
                correlation
            )

            weight_a = invested_weights.get(
                ticker_a,
                0
            )

            weight_b = invested_weights.get(
                ticker_b,
                0
            )

            pair_weight = (
                weight_a
                *
                weight_b
            )

            weighted_corr_sum += (
                correlation
                *
                pair_weight
            )

            pair_weight_sum += (
                pair_weight
            )

            total_portfolio_exposure = sum(
                safe_float(
                    item.get(
                        "final_weight_pct",
                        0
                    )
                )
                for item in positions
                if item.get(
                    "ticker"
                )
                in [
                    ticker_a,
                    ticker_b
                ]
            )

            pairs.append({
                "ticker_a":
                ticker_a,

                "ticker_b":
                ticker_b,

                "correlation":
                round(
                    correlation,
                    3
                ),

                "combined_portfolio_weight_pct":
                round(
                    total_portfolio_exposure,
                    2
                ),

                "risk_level":
                (
                    "VERY_HIGH"
                    if correlation
                    >=
                    VERY_HIGH_CORRELATION_THRESHOLD
                    else
                    "HIGH"
                    if correlation
                    >=
                    HIGH_CORRELATION_THRESHOLD
                    else
                    "NORMAL"
                )
            })

    average_correlation = (
        weighted_corr_sum
        /
        pair_weight_sum
        if pair_weight_sum > 0
        else 0.0
    )

    pairs.sort(
        key=lambda item:
        item.get(
            "correlation",
            -1
        ),
        reverse=True
    )

    return {
        "weighted_average_correlation":
        round(
            average_correlation,
            3
        ),

        "pair_count":
        len(
            pairs
        ),

        "high_correlation_pair_count":
        len([
            pair
            for pair in pairs
            if safe_float(
                pair.get(
                    "correlation"
                )
            )
            >=
            HIGH_CORRELATION_THRESHOLD
        ]),

        "very_high_correlation_pair_count":
        len([
            pair
            for pair in pairs
            if safe_float(
                pair.get(
                    "correlation"
                )
            )
            >=
            VERY_HIGH_CORRELATION_THRESHOLD
        ]),

        "top_pairs":
        pairs[:15],

        "all_pairs":
        pairs
    }


def build_correlation_clusters(
    positions,
    pairwise_analysis
):
    tickers = [
        item.get(
            "ticker"
        )
        for item in positions
        if item.get(
            "ticker"
        )
    ]

    adjacency = {
        ticker:
        set()
        for ticker in tickers
    }

    for pair in (
        pairwise_analysis.get(
            "all_pairs",
            []
        )
        or
        []
    ):
        if safe_float(
            pair.get(
                "correlation",
                0
            )
        ) < HIGH_CORRELATION_THRESHOLD:
            continue

        ticker_a = pair.get(
            "ticker_a"
        )

        ticker_b = pair.get(
            "ticker_b"
        )

        if (
            ticker_a in adjacency
            and
            ticker_b in adjacency
        ):
            adjacency[
                ticker_a
            ].add(
                ticker_b
            )

            adjacency[
                ticker_b
            ].add(
                ticker_a
            )

    position_lookup = {
        item.get(
            "ticker"
        ):
        item
        for item in positions
        if item.get(
            "ticker"
        )
    }

    visited = set()

    clusters = []

    for ticker in tickers:
        if ticker in visited:
            continue

        stack = [
            ticker
        ]

        component = []

        while stack:
            current = stack.pop()

            if current in visited:
                continue

            visited.add(
                current
            )

            component.append(
                current
            )

            stack.extend(
                neighbor
                for neighbor in adjacency.get(
                    current,
                    set()
                )
                if neighbor not in visited
            )

        if len(
            component
        ) < 2:
            continue

        exposure = sum(
            safe_float(
                position_lookup.get(
                    member,
                    {}
                ).get(
                    "final_weight_pct",
                    0
                )
            )
            for member in component
        )

        clusters.append({
            "tickers":
            sorted(
                component
            ),

            "position_count":
            len(
                component
            ),

            "portfolio_weight_pct":
            round(
                exposure,
                2
            ),

            "limit_pct":
            MAX_CLUSTER_EXPOSURE_LIMIT_PCT,

            "status":
            (
                "BREACH"
                if exposure
                >
                MAX_CLUSTER_EXPOSURE_LIMIT_PCT
                else
                "HIGH"
                if exposure
                >=
                45
                else
                "WATCH"
            )
        })

    clusters.sort(
        key=lambda item:
        safe_float(
            item.get(
                "portfolio_weight_pct",
                0
            )
        ),
        reverse=True
    )

    return clusters


def build_portfolio_return_series(
    positions,
    returns_frame
):
    available_positions = [
        item
        for item in positions
        if item.get(
            "ticker"
        )
        in returns_frame.columns
    ]

    if not available_positions:
        return None

    weights = {
        item.get(
            "ticker"
        ):
        safe_float(
            item.get(
                "final_weight_pct",
                0
            )
        )
        /
        100
        for item in available_positions
    }

    aligned = returns_frame[
        list(
            weights.keys()
        )
    ].dropna()

    if len(
        aligned
    ) < MIN_OBSERVATIONS:
        return None

    portfolio_returns = pd.Series(
        0.0,
        index=aligned.index
    )

    for ticker, weight in weights.items():
        portfolio_returns = (
            portfolio_returns
            +
            aligned[
                ticker
            ]
            *
            weight
        )

    portfolio_returns.name = (
        "PORTFOLIO"
    )

    return portfolio_returns


def calculate_factor_sensitivity(
    portfolio_returns,
    factor_returns
):
    if (
        portfolio_returns is None
        or
        factor_returns is None
    ):
        return None

    aligned = pd.concat(
        [
            portfolio_returns,
            factor_returns
        ],
        axis=1,
        join="inner"
    ).dropna()

    if len(
        aligned
    ) < MIN_OBSERVATIONS:
        return None

    portfolio_series = aligned.iloc[
        :,
        0
    ]

    factor_series = aligned.iloc[
        :,
        1
    ]

    variance = factor_series.var()

    beta = (
        portfolio_series.cov(
            factor_series
        )
        /
        variance
        if variance
        and
        not math.isclose(
            variance,
            0
        )
        else 0.0
    )

    correlation = portfolio_series.corr(
        factor_series
    )

    if pd.isna(
        correlation
    ):
        correlation = 0.0

    return {
        "beta":
        round(
            safe_float(
                beta
            ),
            3
        ),

        "correlation":
        round(
            safe_float(
                correlation
            ),
            3
        ),

        "observations":
        len(
            aligned
        )
    }


def calculate_portfolio_volatility(
    portfolio_returns
):
    if portfolio_returns is None:
        return 0.0

    if len(
        portfolio_returns
    ) < MIN_OBSERVATIONS:
        return 0.0

    return round(
        safe_float(
            portfolio_returns.std()
            *
            np.sqrt(
                252
            )
            *
            100
        ),
        2
    )


def calculate_exposure_tables(
    positions
):
    sector_values = {}

    theme_values = {}

    for item in positions:
        weight = safe_float(
            item.get(
                "final_weight_pct",
                0
            )
        )

        sector = (
            item.get(
                "sector"
            )
            or
            "Unknown"
        )

        theme = (
            item.get(
                "theme"
            )
            or
            "Unknown"
        )

        sector_values[
            sector
        ] = (
            sector_values.get(
                sector,
                0
            )
            +
            weight
        )

        theme_values[
            theme
        ] = (
            theme_values.get(
                theme,
                0
            )
            +
            weight
        )

    sectors = [
        {
            "name":
            name,

            "weight_pct":
            round(
                value,
                2
            )
        }
        for name, value in sector_values.items()
    ]

    themes = [
        {
            "name":
            name,

            "weight_pct":
            round(
                value,
                2
            )
        }
        for name, value in theme_values.items()
    ]

    sectors.sort(
        key=lambda item:
        safe_float(
            item.get(
                "weight_pct",
                0
            )
        ),
        reverse=True
    )

    themes.sort(
        key=lambda item:
        safe_float(
            item.get(
                "weight_pct",
                0
            )
        ),
        reverse=True
    )

    ai_complex_weight = sum(
        safe_float(
            item.get(
                "final_weight_pct",
                0
            )
        )
        for item in positions
        if "AI" in str(
            item.get(
                "theme",
                ""
            )
        ).upper()
    )

    return {
        "sector_exposure":
        sectors,

        "theme_exposure":
        themes,

        "ai_complex_weight_pct":
        round(
            ai_complex_weight,
            2
        ),

        "largest_sector":
        (
            sectors[0]
            if sectors
            else None
        ),

        "largest_theme":
        (
            themes[0]
            if themes
            else None
        )
    }


def classify_correlation_risk(
    average_correlation
):
    if average_correlation >= 0.70:
        return "HIGH"

    if average_correlation >= 0.50:
        return "ELEVATED"

    if average_correlation >= 0.30:
        return "MODERATE"

    return "LOW"


def calculate_hidden_risk_score(
    average_correlation,
    max_cluster_weight,
    top_factor_correlation,
    largest_theme_weight
):
    correlation_component = (
        max(
            0,
            min(
                1,
                average_correlation
            )
        )
        *
        35
    )

    cluster_component = (
        min(
            1,
            max_cluster_weight
            /
            MAX_CLUSTER_EXPOSURE_LIMIT_PCT
        )
        *
        30
    )

    factor_component = (
        min(
            1,
            abs(
                top_factor_correlation
            )
        )
        *
        20
    )

    theme_component = (
        min(
            1,
            largest_theme_weight
            /
            THEME_CONCENTRATION_LIMIT_PCT
        )
        *
        15
    )

    return round(
        min(
            100,
            correlation_component
            +
            cluster_component
            +
            factor_component
            +
            theme_component
        ),
        1
    )


def classify_hidden_risk(
    score
):
    if score >= 75:
        return (
            "HIGH",
            "REDUCE_CORRELATED_RISK"
        )

    if score >= 55:
        return (
            "ELEVATED",
            "LIMIT_NEW_CORRELATED_RISK"
        )

    if score >= 35:
        return (
            "MODERATE",
            "MONITOR"
        )

    return (
        "LOW",
        "ACCEPTABLE"
    )


def analyze_portfolio_correlation_factor_risk(
    final_portfolio_projection
):
    positions = (
        get_final_security_positions(
            final_portfolio_projection
        )
    )

    tickers = [
        item.get(
            "ticker"
        )
        for item in positions
        if item.get(
            "ticker"
        )
    ]

    factor_tickers = list(
        FACTOR_PROXIES.values()
    )

    all_tickers = list(
        dict.fromkeys(
            tickers
            +
            factor_tickers
        )
    )

    returns_frame, missing_tickers = (
        build_returns_frame(
            all_tickers
        )
    )

    pairwise_analysis = (
        calculate_pairwise_analysis(
            positions,
            returns_frame
        )
        if not returns_frame.empty
        else {
            "weighted_average_correlation": 0.0,
            "pair_count": 0,
            "high_correlation_pair_count": 0,
            "very_high_correlation_pair_count": 0,
            "top_pairs": [],
            "all_pairs": []
        }
    )

    clusters = build_correlation_clusters(
        positions,
        pairwise_analysis
    )

    portfolio_returns = (
        build_portfolio_return_series(
            positions,
            returns_frame
        )
        if not returns_frame.empty
        else None
    )

    factor_sensitivity = {}

    for factor_name, proxy in (
        FACTOR_PROXIES.items()
    ):
        factor_returns = (
            returns_frame[
                proxy
            ]
            if (
                not returns_frame.empty
                and
                proxy in returns_frame.columns
            )
            else None
        )

        sensitivity = (
            calculate_factor_sensitivity(
                portfolio_returns,
                factor_returns
            )
        )

        factor_sensitivity[
            factor_name
        ] = {
            "proxy":
            proxy,

            "beta":
            (
                sensitivity.get(
                    "beta"
                )
                if sensitivity
                else None
            ),

            "correlation":
            (
                sensitivity.get(
                    "correlation"
                )
                if sensitivity
                else None
            ),

            "observations":
            (
                sensitivity.get(
                    "observations"
                )
                if sensitivity
                else 0
            )
        }

    valid_factors = [
        (
            name,
            data
        )
        for name, data in factor_sensitivity.items()
        if data.get(
            "correlation"
        )
        is not None
    ]

    top_factor = None

    if valid_factors:
        top_factor_name, top_factor_data = max(
            valid_factors,
            key=lambda item:
            abs(
                safe_float(
                    item[1].get(
                        "correlation",
                        0
                    )
                )
            )
        )

        top_factor = {
            "factor":
            top_factor_name,

            **top_factor_data
        }

    exposure_tables = (
        calculate_exposure_tables(
            positions
        )
    )

    average_correlation = safe_float(
        pairwise_analysis.get(
            "weighted_average_correlation",
            0
        )
    )

    max_cluster_weight = (
        safe_float(
            clusters[0].get(
                "portfolio_weight_pct",
                0
            )
        )
        if clusters
        else 0.0
    )

    top_factor_correlation = (
        safe_float(
            (
                top_factor
                or
                {}
            ).get(
                "correlation",
                0
            )
        )
    )

    largest_theme_weight = (
        safe_float(
            (
                exposure_tables.get(
                    "largest_theme"
                )
                or
                {}
            ).get(
                "weight_pct",
                0
            )
        )
    )

    hidden_risk_score = (
        calculate_hidden_risk_score(
            average_correlation,
            max_cluster_weight,
            top_factor_correlation,
            largest_theme_weight
        )
    )

    risk_level, recommendation = (
        classify_hidden_risk(
            hidden_risk_score
        )
    )

    coverage_count = len([
        ticker
        for ticker in tickers
        if ticker in returns_frame.columns
    ]) if not returns_frame.empty else 0

    coverage_pct = (
        coverage_count
        /
        len(
            tickers
        )
        *
        100
        if tickers
        else 0
    )

    return {
        "engine":
        "V7.6 Portfolio Correlation & Factor Risk Engine",

        "timestamp":
        datetime.now(
            timezone.utc
        ).isoformat(),

        "position_count":
        len(
            positions
        ),

        "data_coverage": {
            "positions_with_market_history":
            coverage_count,

            "positions_total":
            len(
                tickers
            ),

            "coverage_pct":
            round(
                coverage_pct,
                1
            ),

            "missing_tickers":
            [
                ticker
                for ticker in missing_tickers
                if ticker in tickers
            ]
        },

        "portfolio_volatility_annualized_pct":
        calculate_portfolio_volatility(
            portfolio_returns
        ),

        "weighted_average_correlation":
        round(
            average_correlation,
            3
        ),

        "correlation_risk":
        classify_correlation_risk(
            average_correlation
        ),

        "high_correlation_pair_count":
        pairwise_analysis.get(
            "high_correlation_pair_count",
            0
        ),

        "very_high_correlation_pair_count":
        pairwise_analysis.get(
            "very_high_correlation_pair_count",
            0
        ),

        "top_correlated_pairs":
        pairwise_analysis.get(
            "top_pairs",
            []
        ),

        "correlation_clusters":
        clusters,

        "largest_cluster_weight_pct":
        round(
            max_cluster_weight,
            2
        ),

        "cluster_limit_pct":
        MAX_CLUSTER_EXPOSURE_LIMIT_PCT,

        "cluster_limit_breached":
        (
            max_cluster_weight
            >
            MAX_CLUSTER_EXPOSURE_LIMIT_PCT
        ),

        "factor_sensitivity":
        factor_sensitivity,

        "dominant_factor":
        top_factor,

        "sector_exposure":
        exposure_tables.get(
            "sector_exposure",
            []
        ),

        "theme_exposure":
        exposure_tables.get(
            "theme_exposure",
            []
        ),

        "ai_complex_weight_pct":
        exposure_tables.get(
            "ai_complex_weight_pct",
            0
        ),

        "largest_sector":
        exposure_tables.get(
            "largest_sector"
        ),

        "largest_theme":
        exposure_tables.get(
            "largest_theme"
        ),

        "hidden_risk_score":
        hidden_risk_score,

        "hidden_risk_level":
        risk_level,

        "recommendation":
        recommendation,

        "note":
        (
            "This layer measures hidden diversification risk using historical "
            "co-movement and factor proxies. It is diagnostic only and does not "
            "automatically liquidate or resize positions."
        )
    }
