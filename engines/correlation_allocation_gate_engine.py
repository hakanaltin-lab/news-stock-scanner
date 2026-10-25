"""
V7.7 AURORA Correlation-Aware Capital Allocation Gate

Purpose:
- Evaluate each actionable BUY / ACCUMULATE candidate before capital allocation
- Measure candidate correlation with the rebalanced existing portfolio
- Measure maximum pairwise correlation with existing holdings
- Estimate high-correlation cluster exposure after adding the candidate
- Detect dominant factor overlap using SPY / QQQ / SMH / XLE
- Produce ALLOW / REDUCE_SIZE / BLOCK policy for capital allocation

Important:
- This engine operates BEFORE new allocations are committed.
- It uses the event-adjusted rebalancing result for existing holdings.
- It does not send broker orders.
"""

from datetime import datetime, timezone

import pandas as pd

from engines.portfolio_correlation_factor_risk_engine import (
    FACTOR_PROXIES,
    HIGH_CORRELATION_THRESHOLD,
    MIN_OBSERVATIONS,
    build_returns_frame,
    build_portfolio_return_series,
    calculate_factor_sensitivity,
    safe_float
)


BUY_TARGET_WEIGHT = 5.0
ACCUMULATE_TARGET_WEIGHT = 4.0

CLUSTER_BLOCK_LIMIT_PCT = 60.0
CLUSTER_REDUCE_LIMIT_PCT = 45.0

PORTFOLIO_CORR_BLOCK = 0.85
PORTFOLIO_CORR_REDUCE = 0.75
PORTFOLIO_CORR_WATCH = 0.65

MAX_PAIR_BLOCK = 0.90
MAX_PAIR_REDUCE = 0.85
MAX_PAIR_WATCH = 0.75


def calculate_weight(
    value,
    portfolio_value
):
    if portfolio_value <= 0:
        return 0.0

    return (
        value
        /
        portfolio_value
        *
        100
    )


def build_rebalanced_positions(
    portfolio_results,
    rebalancing_result
):
    portfolio_value = safe_float(
        rebalancing_result.get(
            "portfolio_value",
            0
        )
    )

    plan_lookup = {
        item.get("ticker"):
        item
        for item in (
            rebalancing_result.get(
                "rebalancing_plan",
                []
            )
            or
            []
        )
        if item.get("ticker")
    }

    positions = []

    for item in portfolio_results:
        ticker = item.get(
            "ticker"
        )

        if not ticker:
            continue

        management = item.get(
            "portfolio_management",
            {}
        )

        position = management.get(
            "position",
            {}
        )

        current_value = safe_float(
            position.get(
                "current_value",
                0
            )
        )

        plan = plan_lookup.get(
            ticker,
            {}
        )

        projected_value = safe_float(
            plan.get(
                "projected_value",
                current_value
            )
        )

        if projected_value <= 0:
            continue

        holding = item.get(
            "holding",
            {}
        )

        positions.append({
            "ticker":
            ticker,

            "sector":
            holding.get(
                "sector",
                "Unknown"
            ),

            "theme":
            holding.get(
                "theme",
                "Unknown"
            ),

            "final_value":
            round(
                projected_value,
                2
            ),

            "final_weight_pct":
            round(
                calculate_weight(
                    projected_value,
                    portfolio_value
                ),
                2
            )
        })

    return positions


def provisional_target_weight(
    opportunity,
    market_regime_result,
    event_risk_result
):
    action = opportunity.get(
        "action",
        "WATCH"
    )

    if action == "BUY":
        base_weight = BUY_TARGET_WEIGHT
    elif action == "ACCUMULATE":
        base_weight = ACCUMULATE_TARGET_WEIGHT
    else:
        return 0.0

    regime_policy = (
        (
            market_regime_result
            or
            {}
        ).get(
            "policy",
            {}
        )
        or
        {}
    )

    regime_multiplier = safe_float(
        regime_policy.get(
            "position_size_multiplier",
            1.0
        ),
        1.0
    )

    max_new_weight = safe_float(
        regime_policy.get(
            "max_new_position_weight_pct",
            5.0
        ),
        5.0
    )

    weight = min(
        base_weight
        *
        regime_multiplier,
        max_new_weight
    )

    ticker = opportunity.get(
        "ticker"
    )

    event_combined = (
        (
            (
                event_risk_result
                or
                {}
            ).get(
                "ticker_risk",
                {}
            )
            or
            {}
        ).get(
            ticker,
            {}
        ).get(
            "combined",
            {}
        )
        or
        {}
    )

    event_multiplier = safe_float(
        event_combined.get(
            "position_size_multiplier",
            1.0
        ),
        1.0
    )

    return round(
        weight
        *
        event_multiplier,
        2
    )


def calculate_candidate_pair_correlations(
    candidate,
    existing_positions,
    returns_frame
):
    if candidate not in returns_frame.columns:
        return []

    results = []

    candidate_series = returns_frame[
        candidate
    ]

    for position in existing_positions:
        ticker = position.get(
            "ticker"
        )

        if (
            not ticker
            or
            ticker not in returns_frame.columns
        ):
            continue

        aligned = pd.concat(
            [
                candidate_series,
                returns_frame[
                    ticker
                ]
            ],
            axis=1,
            join="inner"
        ).dropna()

        if len(
            aligned
        ) < MIN_OBSERVATIONS:
            continue

        correlation = aligned.iloc[
            :,
            0
        ].corr(
            aligned.iloc[
                :,
                1
            ]
        )

        if pd.isna(
            correlation
        ):
            continue

        results.append({
            "ticker":
            ticker,

            "correlation":
            round(
                float(
                    correlation
                ),
                3
            ),

            "existing_weight_pct":
            safe_float(
                position.get(
                    "final_weight_pct",
                    0
                )
            )
        })

    results.sort(
        key=lambda item:
        item.get(
            "correlation",
            -1
        ),
        reverse=True
    )

    return results


def calculate_direct_correlation(
    series_a,
    series_b
):
    if (
        series_a is None
        or
        series_b is None
    ):
        return None

    aligned = pd.concat(
        [
            series_a,
            series_b
        ],
        axis=1,
        join="inner"
    ).dropna()

    if len(
        aligned
    ) < MIN_OBSERVATIONS:
        return None

    correlation = aligned.iloc[
        :,
        0
    ].corr(
        aligned.iloc[
            :,
            1
        ]
    )

    if pd.isna(
        correlation
    ):
        return None

    return float(
        correlation
    )


def get_factor_profile(
    series,
    returns_frame
):
    profile = {}

    for factor_name, proxy in (
        FACTOR_PROXIES.items()
    ):
        factor_series = (
            returns_frame[
                proxy
            ]
            if proxy in returns_frame.columns
            else None
        )

        correlation = calculate_direct_correlation(
            series,
            factor_series
        )

        profile[
            factor_name
        ] = {
            "proxy":
            proxy,

            "correlation":
            (
                round(
                    correlation,
                    3
                )
                if correlation is not None
                else None
            )
        }

    valid = [
        (
            name,
            item
        )
        for name, item in profile.items()
        if item.get(
            "correlation"
        )
        is not None
    ]

    dominant = None

    if valid:
        name, item = max(
            valid,
            key=lambda pair:
            abs(
                safe_float(
                    pair[1].get(
                        "correlation",
                        0
                    )
                )
            )
        )

        dominant = {
            "factor":
            name,

            **item
        }

    return (
        profile,
        dominant
    )


def determine_gate_policy(
    candidate_portfolio_corr,
    max_pair_corr,
    projected_cluster_weight,
    factor_overlap
):
    reasons = []

    if (
        projected_cluster_weight
        >
        CLUSTER_BLOCK_LIMIT_PCT
        and
        max_pair_corr
        >=
        HIGH_CORRELATION_THRESHOLD
    ):
        reasons.append(
            "Projected high-correlation cluster would exceed 60% of portfolio"
        )

        return {
            "policy": "BLOCK",
            "size_multiplier": 0.0,
            "risk_level": "HIGH",
            "reasons": reasons
        }

    if (
        candidate_portfolio_corr
        >=
        PORTFOLIO_CORR_BLOCK
        and
        max_pair_corr
        >=
        MAX_PAIR_REDUCE
        and
        factor_overlap
    ):
        reasons.append(
            "Candidate is extremely correlated with the portfolio and its dominant factor"
        )

        return {
            "policy": "BLOCK",
            "size_multiplier": 0.0,
            "risk_level": "HIGH",
            "reasons": reasons
        }

    if (
        projected_cluster_weight
        >=
        CLUSTER_REDUCE_LIMIT_PCT
        or
        candidate_portfolio_corr
        >=
        PORTFOLIO_CORR_REDUCE
        or
        max_pair_corr
        >=
        MAX_PAIR_REDUCE
    ):
        reasons.append(
            "Candidate would materially increase correlated portfolio risk"
        )

        if factor_overlap:
            reasons.append(
                "Candidate shares the portfolio dominant factor"
            )

        return {
            "policy": "REDUCE_SIZE",
            "size_multiplier": 0.50,
            "risk_level": "ELEVATED",
            "reasons": reasons
        }

    if (
        candidate_portfolio_corr
        >=
        PORTFOLIO_CORR_WATCH
        or
        max_pair_corr
        >=
        MAX_PAIR_WATCH
        or
        factor_overlap
    ):
        reasons.append(
            "Candidate adds moderate correlation or factor overlap"
        )

        return {
            "policy": "REDUCE_SIZE",
            "size_multiplier": 0.75,
            "risk_level": "MODERATE",
            "reasons": reasons
        }

    return {
        "policy": "ALLOW",
        "size_multiplier": 1.0,
        "risk_level": "LOW",
        "reasons": [
            "No material correlation concentration detected"
        ]
    }


def analyze_candidate(
    opportunity,
    existing_positions,
    portfolio_returns,
    portfolio_dominant_factor,
    returns_frame,
    market_regime_result,
    event_risk_result
):
    ticker = opportunity.get(
        "ticker"
    )

    target_weight = provisional_target_weight(
        opportunity,
        market_regime_result,
        event_risk_result
    )

    if (
        not ticker
        or
        ticker not in returns_frame.columns
    ):
        return {
            "ticker":
            ticker,

            "policy":
            "REDUCE_SIZE",

            "risk_level":
            "DATA_REVIEW",

            "size_multiplier":
            0.75,

            "provisional_target_weight_pct":
            target_weight,

            "candidate_portfolio_correlation":
            None,

            "max_pair_correlation":
            None,

            "high_correlation_existing_weight_pct":
            0.0,

            "projected_cluster_weight_pct":
            target_weight,

            "dominant_factor":
            None,

            "portfolio_dominant_factor":
            portfolio_dominant_factor,

            "factor_overlap":
            False,

            "reasons": [
                "Insufficient historical data for full correlation check"
            ]
        }

    candidate_series = returns_frame[
        ticker
    ]

    candidate_portfolio_corr = (
        calculate_direct_correlation(
            candidate_series,
            portfolio_returns
        )
    )

    if candidate_portfolio_corr is None:
        candidate_portfolio_corr = 0.0

    pairs = (
        calculate_candidate_pair_correlations(
            ticker,
            existing_positions,
            returns_frame
        )
    )

    max_pair_corr = (
        safe_float(
            pairs[0].get(
                "correlation",
                0
            )
        )
        if pairs
        else 0.0
    )

    high_corr_holdings = [
        item
        for item in pairs
        if safe_float(
            item.get(
                "correlation",
                0
            )
        )
        >=
        HIGH_CORRELATION_THRESHOLD
    ]

    high_corr_existing_weight = sum(
        safe_float(
            item.get(
                "existing_weight_pct",
                0
            )
        )
        for item in high_corr_holdings
    )

    projected_cluster_weight = (
        high_corr_existing_weight
        +
        target_weight
    )

    candidate_factor_profile, candidate_dominant_factor = (
        get_factor_profile(
            candidate_series,
            returns_frame
        )
    )

    factor_overlap = False

    if (
        candidate_dominant_factor
        and
        portfolio_dominant_factor
        and
        candidate_dominant_factor.get(
            "factor"
        )
        ==
        portfolio_dominant_factor.get(
            "factor"
        )
        and
        abs(
            safe_float(
                candidate_dominant_factor.get(
                    "correlation",
                    0
                )
            )
        )
        >=
        0.80
        and
        abs(
            safe_float(
                portfolio_dominant_factor.get(
                    "correlation",
                    0
                )
            )
        )
        >=
        0.80
    ):
        factor_overlap = True

    policy = determine_gate_policy(
        candidate_portfolio_corr,
        max_pair_corr,
        projected_cluster_weight,
        factor_overlap
    )

    return {
        "ticker":
        ticker,

        "policy":
        policy.get(
            "policy"
        ),

        "risk_level":
        policy.get(
            "risk_level"
        ),

        "size_multiplier":
        policy.get(
            "size_multiplier"
        ),

        "provisional_target_weight_pct":
        target_weight,

        "candidate_portfolio_correlation":
        round(
            candidate_portfolio_corr,
            3
        ),

        "max_pair_correlation":
        round(
            max_pair_corr,
            3
        ),

        "max_pair_ticker":
        (
            pairs[0].get(
                "ticker"
            )
            if pairs
            else None
        ),

        "high_correlation_existing_weight_pct":
        round(
            high_corr_existing_weight,
            2
        ),

        "projected_cluster_weight_pct":
        round(
            projected_cluster_weight,
            2
        ),

        "high_correlation_holdings":
        high_corr_holdings,

        "factor_profile":
        candidate_factor_profile,

        "dominant_factor":
        candidate_dominant_factor,

        "portfolio_dominant_factor":
        portfolio_dominant_factor,

        "factor_overlap":
        factor_overlap,

        "reasons":
        policy.get(
            "reasons",
            []
        )
    }


def build_correlation_allocation_gate(
    portfolio_results,
    rebalancing_result,
    opportunity_analysis,
    market_regime_result=None,
    event_risk_result=None
):
    existing_positions = (
        build_rebalanced_positions(
            portfolio_results,
            rebalancing_result
        )
    )

    actionable = list(
        opportunity_analysis.get(
            "top_actionable",
            []
        )
        or
        []
    )

    existing_tickers = [
        item.get(
            "ticker"
        )
        for item in existing_positions
        if item.get(
            "ticker"
        )
    ]

    candidate_tickers = [
        item.get(
            "ticker"
        )
        for item in actionable
        if item.get(
            "ticker"
        )
    ]

    all_tickers = list(
        dict.fromkeys(
            existing_tickers
            +
            candidate_tickers
            +
            list(
                FACTOR_PROXIES.values()
            )
        )
    )

    returns_frame, missing_tickers = (
        build_returns_frame(
            all_tickers
        )
    )

    portfolio_returns = (
        build_portfolio_return_series(
            existing_positions,
            returns_frame
        )
        if not returns_frame.empty
        else None
    )

    portfolio_factor_profile = {}

    portfolio_dominant_factor = None

    if portfolio_returns is not None:
        for factor_name, proxy in (
            FACTOR_PROXIES.items()
        ):
            factor_returns = (
                returns_frame[
                    proxy
                ]
                if proxy in returns_frame.columns
                else None
            )

            sensitivity = (
                calculate_factor_sensitivity(
                    portfolio_returns,
                    factor_returns
                )
            )

            portfolio_factor_profile[
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
                )
            }

        valid = [
            (
                name,
                item
            )
            for name, item in (
                portfolio_factor_profile.items()
            )
            if item.get(
                "correlation"
            )
            is not None
        ]

        if valid:
            name, item = max(
                valid,
                key=lambda pair:
                abs(
                    safe_float(
                        pair[1].get(
                            "correlation",
                            0
                        )
                    )
                )
            )

            portfolio_dominant_factor = {
                "factor":
                name,

                **item
            }

    candidate_results = {}

    for opportunity in actionable:
        ticker = opportunity.get(
            "ticker"
        )

        if not ticker:
            continue

        candidate_results[
            ticker
        ] = analyze_candidate(
            opportunity=opportunity,
            existing_positions=existing_positions,
            portfolio_returns=portfolio_returns,
            portfolio_dominant_factor=portfolio_dominant_factor,
            returns_frame=returns_frame,
            market_regime_result=market_regime_result,
            event_risk_result=event_risk_result
        )

    blocked = [
        item
        for item in candidate_results.values()
        if item.get(
            "policy"
        )
        ==
        "BLOCK"
    ]

    reduced = [
        item
        for item in candidate_results.values()
        if item.get(
            "policy"
        )
        ==
        "REDUCE_SIZE"
    ]

    return {
        "engine":
        "V7.7 Correlation-Aware Capital Allocation Gate",

        "timestamp":
        datetime.now(
            timezone.utc
        ).isoformat(),

        "existing_position_count":
        len(
            existing_positions
        ),

        "actionable_candidate_count":
        len(
            actionable
        ),

        "portfolio_factor_profile":
        portfolio_factor_profile,

        "portfolio_dominant_factor":
        portfolio_dominant_factor,

        "blocked_count":
        len(
            blocked
        ),

        "reduced_count":
        len(
            reduced
        ),

        "candidate_risk":
        candidate_results,

        "missing_tickers":
        missing_tickers,

        "policy": {
            "cluster_block_limit_pct":
            CLUSTER_BLOCK_LIMIT_PCT,

            "cluster_reduce_limit_pct":
            CLUSTER_REDUCE_LIMIT_PCT,

            "portfolio_corr_block":
            PORTFOLIO_CORR_BLOCK,

            "portfolio_corr_reduce":
            PORTFOLIO_CORR_REDUCE,

            "portfolio_corr_watch":
            PORTFOLIO_CORR_WATCH,

            "high_correlation_threshold":
            HIGH_CORRELATION_THRESHOLD
        }
    }
