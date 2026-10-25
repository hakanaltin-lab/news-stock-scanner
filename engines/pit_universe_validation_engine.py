"""
V8.6 AURORA Point-in-Time Neutral Universe Validation

Purpose:
- Reduce current-portfolio survivorship / selection bias in historical testing.
- Use point-in-time S&P 500 and Nasdaq-100 membership snapshots.
- Rank only securities that were members of the index at the decision date.
- Use only historical price/risk features available before execution.
- Compare:
    1) AURORA strategic Top-12, fully invested
    2) AURORA strategic Top-12 + V7.9 risk overlay
    3) Point-in-time equal-weight universe control
    4) Market benchmark (SPY or QQQ)

Scope:
- Historical fundamentals/news/events are intentionally excluded because
  reliable point-in-time archives are not yet connected.
- Membership history is pinned to a specific external Git commit for
  reproducibility.
- Test end is capped before the pinned source commit date.
- Yahoo Finance may not provide complete delisted/security-history coverage.
  Coverage is measured and reported explicitly.

No broker orders are sent.
"""

from datetime import datetime, timezone
import csv
import io
import json
import math
import os

import pandas as pd
import requests
import yfinance as yf

from engines.walk_forward_backtest_engine import (
    calculate_equity_metrics,
    replay_action,
    exposure_multiplier,
    safe_float,
    strategic_state_as_of
)


ENGINE_VERSION = (
    "V8.6 Point-in-Time Neutral Universe Validation"
)

VALIDATION_SIGNATURE = "V8.6.1"

OUTPUT_FILE = (
    "docs/pit_universe_validation.json"
)

SOURCE_REPOSITORY = (
    "thuningxu/sp500nq100"
)

SOURCE_COMMIT = (
    "1cc1de2770874293597a418b41b079e5337b260c"
)

SOURCE_BASE_URL = (
    "https://raw.githubusercontent.com/"
    + SOURCE_REPOSITORY
    + "/"
    + SOURCE_COMMIT
    + "/"
)

SOURCE_FILES = {
    "SP500":
    "sp500_components_history.csv",

    "NASDAQ100":
    "nasdaq100_components_history.csv"
}

TEST_START = "2022-06-01"

TEST_END = "2026-06-05"

DOWNLOAD_START = "2021-01-01"

DOWNLOAD_END = "2026-06-08"

TOP_N = 12

MIN_WARMUP_SESSIONS = 252

TRADING_FRICTION_BPS = 10.0

BATCH_SIZE = 60

REQUEST_TIMEOUT_SECONDS = 30


def normalize_symbol(
    ticker
):
    ticker = str(
        ticker
        or
        ""
    ).strip().upper()

    if not ticker:
        return None

    return ticker.replace(
        ".",
        "-"
    )


def parse_membership_csv(
    text
):
    reader = csv.DictReader(
        io.StringIO(
            text
        )
    )

    rows = []

    for row in reader:
        try:
            date_value = pd.Timestamp(
                row.get(
                    "date"
                )
            )
        except Exception:
            continue

        tickers = [
            normalize_symbol(
                item
            )
            for item in str(
                row.get(
                    "tickers",
                    ""
                )
            ).split(
                ","
            )
        ]

        tickers = sorted(
            set(
                item
                for item in tickers
                if item
            )
        )

        if not tickers:
            continue

        rows.append({
            "date":
            date_value,

            "tickers":
            tickers
        })

    rows.sort(
        key=lambda item:
        item[
            "date"
        ]
    )

    return rows


def fetch_membership_history(
    filename
):
    url = (
        SOURCE_BASE_URL
        +
        filename
    )

    response = requests.get(
        url,
        timeout=REQUEST_TIMEOUT_SECONDS
    )

    response.raise_for_status()

    return parse_membership_csv(
        response.text
    )


def membership_on(
    history,
    date_value
):
    selected = None

    for row in history:
        if (
            row[
                "date"
            ]
            <=
            date_value
        ):
            selected = row[
                "tickers"
            ]
        else:
            break

    return list(
        selected
        or
        []
    )


def unique_members_during_test(
    history
):
    start = pd.Timestamp(
        TEST_START
    )

    end = pd.Timestamp(
        TEST_END
    )

    dates = [
        start,
        end
    ]

    dates.extend(
        row[
            "date"
        ]
        for row in history
        if (
            row[
                "date"
            ]
            >=
            start
            and
            row[
                "date"
            ]
            <=
            end
        )
    )

    members = set()

    for date_value in dates:
        members.update(
            membership_on(
                history,
                date_value
            )
        )

    return sorted(
        members
    )


def extract_close_series(
    data,
    ticker,
    batch_count
):
    try:
        if isinstance(
            data.columns,
            pd.MultiIndex
        ):
            level_zero = set(
                data.columns.get_level_values(
                    0
                )
            )

            level_one = set(
                data.columns.get_level_values(
                    1
                )
            )

            if ticker in level_zero:
                series = data[
                    ticker
                ][
                    "Close"
                ]

            elif ticker in level_one:
                series = data.xs(
                    ticker,
                    axis=1,
                    level=1
                )[
                    "Close"
                ]

            else:
                return None

        else:
            if (
                batch_count
                !=
                1
                or
                "Close"
                not in data.columns
            ):
                return None

            series = data[
                "Close"
            ]

        clean = series.dropna()

        if clean.empty:
            return None

        return clean.astype(
            float
        )

    except Exception:
        return None


def download_price_frame(
    tickers
):
    tickers = sorted(
        set(
            item
            for item in tickers
            if item
        )
    )

    close_data = {}

    for start in range(
        0,
        len(
            tickers
        ),
        BATCH_SIZE
    ):
        batch = tickers[
            start:
            start
            +
            BATCH_SIZE
        ]

        try:
            data = yf.download(
                tickers=batch,
                start=DOWNLOAD_START,
                end=DOWNLOAD_END,
                interval="1d",
                auto_adjust=True,
                progress=False,
                threads=True,
                group_by="ticker"
            )

        except Exception:
            continue

        if data is None or data.empty:
            continue

        for ticker in batch:
            series = extract_close_series(
                data,
                ticker,
                len(
                    batch
                )
            )

            if series is None:
                continue

            close_data[
                ticker
            ] = series

    if not close_data:
        return pd.DataFrame()

    frame = pd.DataFrame(
        close_data
    ).sort_index()

    if isinstance(
        frame.index,
        pd.DatetimeIndex
    ):
        try:
            frame.index = (
                frame.index.tz_localize(
                    None
                )
            )
        except Exception:
            pass

    return frame


def first_trading_day_each_month(
    spy_index
):
    start = pd.Timestamp(
        TEST_START
    )

    end = pd.Timestamp(
        TEST_END
    )

    dates = [
        item
        for item in spy_index
        if (
            item
            >=
            start
            and
            item
            <=
            end
        )
    ]

    by_month = {}

    for date_value in dates:
        key = (
            date_value.year,
            date_value.month
        )

        if key not in by_month:
            by_month[
                key
            ] = date_value

    return [
        by_month[
            key
        ]
        for key in sorted(
            by_month
        )
    ]


def previous_trading_date(
    trading_index,
    date_value
):
    eligible = [
        item
        for item in trading_index
        if item < date_value
    ]

    if not eligible:
        return None

    return eligible[
        -1
    ]


def exact_price(
    raw_frame,
    ticker,
    date_value
):
    if ticker not in raw_frame.columns:
        return None

    try:
        value = raw_frame.loc[
            date_value,
            ticker
        ]
    except Exception:
        return None

    value = safe_float(
        value,
        None
    )

    if (
        value is None
        or
        pd.isna(
            value
        )
        or
        value <= 0
    ):
        return None

    return value


def valuation_price(
    valuation_frame,
    ticker,
    date_value
):
    if ticker not in valuation_frame.columns:
        return None

    try:
        value = valuation_frame.loc[
            date_value,
            ticker
        ]
    except Exception:
        return None

    value = safe_float(
        value,
        None
    )

    if (
        value is None
        or
        pd.isna(
            value
        )
        or
        value <= 0
    ):
        return None

    return value


def eligible_state(
    ticker,
    decision_date,
    close_frame
):
    if ticker not in close_frame.columns:
        return None

    history = close_frame[
        ticker
    ].loc[
        :decision_date
    ].dropna()

    if len(
        history
    ) < MIN_WARMUP_SESSIONS:
        return None

    state = strategic_state_as_of(
        ticker,
        decision_date,
        close_frame
    )

    if not state:
        return None

    trend_score = safe_float(
        state.get(
            "trend_score"
        ),
        50
    )

    risk_score = safe_float(
        state.get(
            "risk_score"
        ),
        50
    )

    # V7.9 strategic composite with historical catalyst/sector unavailable.
    # Both omitted components are held neutral at 50.
    composite = (
        trend_score
        *
        0.55
        +
        risk_score
        *
        0.20
        +
        50
        *
        0.15
        +
        50
        *
        0.10
    )

    return {
        **state,

        "neutralized_strategic_composite":
        round(
            composite,
            2
        ),

        "replay_action":
        replay_action(
            state
        )
    }


def score_point_in_time_universe(
    members,
    decision_date,
    close_frame
):
    rows = []

    for ticker in members:
        state = eligible_state(
            ticker,
            decision_date,
            close_frame
        )

        if not state:
            continue

        rows.append(
            state
        )

    rows.sort(
        key=lambda item: (
            safe_float(
                item.get(
                    "neutralized_strategic_composite"
                ),
                0
            ),
            safe_float(
                item.get(
                    "relative_strength_6m_pct"
                ),
                -999
            )
        ),
        reverse=True
    )

    return rows


def target_weights(
    mode,
    scored_rows
):
    if not scored_rows:
        return {}

    if mode == "UNIVERSE_EQUAL_WEIGHT":
        weight = (
            1.0
            /
            len(
                scored_rows
            )
        )

        return {
            row[
                "ticker"
            ]:
            weight
            for row in scored_rows
        }

    selected = scored_rows[
        :TOP_N
    ]

    if not selected:
        return {}

    base_weight = (
        1.0
        /
        len(
            selected
        )
    )

    if mode == "TOP12_FULL":
        return {
            row[
                "ticker"
            ]:
            base_weight
            for row in selected
        }

    if mode == "TOP12_RISK_OVERLAY":
        weights = {}

        for row in selected:
            action = row.get(
                "replay_action",
                "WATCH"
            )

            weights[
                row[
                    "ticker"
                ]
            ] = (
                base_weight
                *
                exposure_multiplier(
                    action
                )
            )

        return weights

    return {}


def simulate_mode(
    history,
    close_frame,
    benchmark_ticker,
    mode
):
    benchmark = close_frame[
        benchmark_ticker
    ].dropna()

    trading_dates = [
        item
        for item in benchmark.index
        if (
            item
            >=
            pd.Timestamp(
                TEST_START
            )
            and
            item
            <=
            pd.Timestamp(
                TEST_END
            )
        )
    ]

    if len(
        trading_dates
    ) < 100:
        return None

    rebalance_dates = set(
        first_trading_day_each_month(
            benchmark.index
        )
    )

    valuation_frame = (
        close_frame.ffill()
    )

    capital = 100000.0

    cash = capital

    shares = {}

    total_costs = 0.0

    turnover_notional = 0.0

    equity_points = {}

    coverage_rows = []

    selection_rows = []

    rebalance_count = 0

    for date_value in trading_dates:
        current_value = cash

        for ticker, quantity in (
            shares.items()
        ):
            price = valuation_price(
                valuation_frame,
                ticker,
                date_value
            )

            if price is None:
                continue

            current_value += (
                quantity
                *
                price
            )

        capital = current_value

        if date_value in rebalance_dates:
            decision_date = (
                previous_trading_date(
                    benchmark.index,
                    date_value
                )
            )

            if decision_date is not None:
                members = membership_on(
                    history,
                    decision_date
                )

                scored = (
                    score_point_in_time_universe(
                        members,
                        decision_date,
                        close_frame
                    )
                )

                eligible_for_execution = [
                    row
                    for row in scored
                    if exact_price(
                        close_frame,
                        row[
                            "ticker"
                        ],
                        date_value
                    )
                    is not None
                ]

                coverage_pct = (
                    len(
                        eligible_for_execution
                    )
                    /
                    len(
                        members
                    )
                    *
                    100
                    if members
                    else 0
                )

                coverage_rows.append({
                    "execution_date":
                    str(
                        date_value.date()
                    ),

                    "decision_date":
                    str(
                        decision_date.date()
                    ),

                    "pit_member_count":
                    len(
                        members
                    ),

                    "eligible_count":
                    len(
                        eligible_for_execution
                    ),

                    "coverage_pct":
                    round(
                        coverage_pct,
                        2
                    )
                })

                weights = target_weights(
                    mode,
                    eligible_for_execution
                )

                if weights:
                    rebalance_count += 1

                    if mode != "UNIVERSE_EQUAL_WEIGHT":
                        selection_rows.append({
                            "execution_date":
                            str(
                                date_value.date()
                            ),

                            "selected":
                            [
                                {
                                    "ticker":
                                    row.get(
                                        "ticker"
                                    ),

                                    "score":
                                    row.get(
                                        "neutralized_strategic_composite"
                                    ),

                                    "action":
                                    row.get(
                                        "replay_action"
                                    )
                                }
                                for row in (
                                    eligible_for_execution[
                                        :TOP_N
                                    ]
                                )
                            ]
                        })

                    pre_trade_value = (
                        capital
                    )

                    traded_notional = 0.0

                    all_symbols = set(
                        shares
                    ) | set(
                        weights
                    )

                    for ticker in all_symbols:
                        price = exact_price(
                            close_frame,
                            ticker,
                            date_value
                        )

                        if price is None:
                            price = valuation_price(
                                valuation_frame,
                                ticker,
                                date_value
                            )

                        if price is None:
                            continue

                        current_position_value = (
                            shares.get(
                                ticker,
                                0.0
                            )
                            *
                            price
                        )

                        target_value = (
                            pre_trade_value
                            *
                            weights.get(
                                ticker,
                                0.0
                            )
                        )

                        traded_notional += abs(
                            target_value
                            -
                            current_position_value
                        )

                    trading_cost = (
                        traded_notional
                        *
                        TRADING_FRICTION_BPS
                        /
                        10000
                    )

                    post_cost_value = max(
                        0.0,
                        pre_trade_value
                        -
                        trading_cost
                    )

                    new_shares = {}

                    invested_value = 0.0

                    for ticker, weight in (
                        weights.items()
                    ):
                        price = exact_price(
                            close_frame,
                            ticker,
                            date_value
                        )

                        if (
                            price is None
                            or
                            price <= 0
                        ):
                            continue

                        target_value = (
                            post_cost_value
                            *
                            weight
                        )

                        quantity = (
                            target_value
                            /
                            price
                        )

                        new_shares[
                            ticker
                        ] = quantity

                        invested_value += (
                            target_value
                        )

                    shares = new_shares

                    cash = max(
                        0.0,
                        post_cost_value
                        -
                        invested_value
                    )

                    total_costs += (
                        trading_cost
                    )

                    turnover_notional += (
                        traded_notional
                    )

        current_value = cash

        for ticker, quantity in (
            shares.items()
        ):
            price = valuation_price(
                valuation_frame,
                ticker,
                date_value
            )

            if price is None:
                continue

            current_value += (
                quantity
                *
                price
            )

        equity_points[
            date_value
        ] = current_value

    equity = pd.Series(
        equity_points
    ).sort_index()

    benchmark_start = safe_float(
        benchmark.loc[
            trading_dates[
                0
            ]
        ]
    )

    benchmark_equity = (
        benchmark.reindex(
            equity.index
        )
        /
        benchmark_start
        *
        100000.0
    )

    metrics = calculate_equity_metrics(
        equity,
        benchmark_equity,
        total_costs,
        turnover_notional,
        100000.0
    )

    coverage_values = [
        safe_float(
            row.get(
                "coverage_pct"
            ),
            0
        )
        for row in coverage_rows
    ]

    coverage_summary = {
        "rebalance_observations":
        len(
            coverage_rows
        ),

        "average_coverage_pct":
        (
            round(
                sum(
                    coverage_values
                )
                /
                len(
                    coverage_values
                ),
                2
            )
            if coverage_values
            else None
        ),

        "minimum_coverage_pct":
        (
            round(
                min(
                    coverage_values
                ),
                2
            )
            if coverage_values
            else None
        ),

        "maximum_coverage_pct":
        (
            round(
                max(
                    coverage_values
                ),
                2
            )
            if coverage_values
            else None
        )
    }

    return {
        "mode":
        mode,

        "performance":
        metrics,

        "rebalance_count":
        rebalance_count,

        "coverage":
        coverage_summary,

        "coverage_history":
        coverage_rows,

        "selection_samples":
        selection_rows[
            -6:
        ]
    }


def validate_index(
    index_name,
    history,
    close_frame,
    benchmark_ticker
):
    full = simulate_mode(
        history,
        close_frame,
        benchmark_ticker,
        "TOP12_FULL"
    )

    overlay = simulate_mode(
        history,
        close_frame,
        benchmark_ticker,
        "TOP12_RISK_OVERLAY"
    )

    universe_control = simulate_mode(
        history,
        close_frame,
        benchmark_ticker,
        "UNIVERSE_EQUAL_WEIGHT"
    )

    if (
        full is None
        or
        overlay is None
        or
        universe_control is None
    ):
        return {
            "index":
            index_name,

            "status":
            "INSUFFICIENT_DATA"
        }

    full_metrics = (
        full.get(
            "performance",
            {}
        )
        or
        {}
    )

    overlay_metrics = (
        overlay.get(
            "performance",
            {}
        )
        or
        {}
    )

    control_metrics = (
        universe_control.get(
            "performance",
            {}
        )
        or
        {}
    )

    ranking_alpha = (
        safe_float(
            full_metrics.get(
                "cagr_pct"
            ),
            0
        )
        -
        safe_float(
            control_metrics.get(
                "cagr_pct"
            ),
            0
        )
    )

    overlay_vs_full = (
        safe_float(
            overlay_metrics.get(
                "cagr_pct"
            ),
            0
        )
        -
        safe_float(
            full_metrics.get(
                "cagr_pct"
            ),
            0
        )
    )

    overlay_dd_improvement = (
        safe_float(
            full_metrics.get(
                "max_drawdown_pct"
            ),
            0
        )
        -
        safe_float(
            overlay_metrics.get(
                "max_drawdown_pct"
            ),
            0
        )
    )

    if (
        ranking_alpha > 2
        and
        safe_float(
            full_metrics.get(
                "sharpe_ratio"
            ),
            0
        )
        >
        safe_float(
            control_metrics.get(
                "sharpe_ratio"
            ),
            0
        )
    ):
        ranking_verdict = (
            "RANKING_ADDS_VALUE"
        )

    elif ranking_alpha < -2:
        ranking_verdict = (
            "RANKING_NOT_VALIDATED"
        )

    else:
        ranking_verdict = (
            "RANKING_INCONCLUSIVE"
        )

    if (
        overlay_vs_full >= 0
        and
        overlay_dd_improvement > 0
    ):
        overlay_verdict = (
            "OVERLAY_ADDS_VALUE"
        )

    elif (
        overlay_vs_full < -3
        and
        overlay_dd_improvement <= 2
    ):
        overlay_verdict = (
            "OVERLAY_NOT_VALIDATED"
        )

    else:
        overlay_verdict = (
            "OVERLAY_RISK_RETURN_TRADEOFF"
        )

    return {
        "index":
        index_name,

        "status":
        "COMPLETE",

        "benchmark":
        benchmark_ticker,

        "top_n":
        TOP_N,

        "ranked_top12_full":
        full,

        "ranked_top12_risk_overlay":
        overlay,

        "pit_equal_weight_control":
        universe_control,

        "comparison": {
            "ranking_cagr_alpha_vs_pit_equal_weight_pct":
            round(
                ranking_alpha,
                2
            ),

            "ranking_sharpe_advantage":
            round(
                safe_float(
                    full_metrics.get(
                        "sharpe_ratio"
                    ),
                    0
                )
                -
                safe_float(
                    control_metrics.get(
                        "sharpe_ratio"
                    ),
                    0
                ),
                3
            ),

            "risk_overlay_cagr_effect_vs_full_pct":
            round(
                overlay_vs_full,
                2
            ),

            "risk_overlay_drawdown_improvement_pct":
            round(
                overlay_dd_improvement,
                2
            ),

            "risk_overlay_sharpe_effect":
            round(
                safe_float(
                    overlay_metrics.get(
                        "sharpe_ratio"
                    ),
                    0
                )
                -
                safe_float(
                    full_metrics.get(
                        "sharpe_ratio"
                    ),
                    0
                ),
                3
            )
        },

        "ranking_verdict":
        ranking_verdict,

        "risk_overlay_verdict":
        overlay_verdict
    }


def load_cached_result():
    if not os.path.exists(
        OUTPUT_FILE
    ):
        return None

    try:
        with open(
            OUTPUT_FILE,
            "r",
            encoding="utf-8"
        ) as file:
            data = json.load(
                file
            )

        if (
            data.get(
                "validation_signature"
            )
            !=
            VALIDATION_SIGNATURE
        ):
            return None

        if (
            data.get(
                "source_commit"
            )
            !=
            SOURCE_COMMIT
        ):
            return None

        data[
            "cache_status"
        ] = "REUSED"

        return data

    except Exception:
        return None


def save_result(
    result
):
    os.makedirs(
        os.path.dirname(
            OUTPUT_FILE
        ),
        exist_ok=True
    )

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8"
    ) as file:
        json.dump(
            result,
            file,
            indent=2,
            ensure_ascii=False
        )


def run_pit_universe_validation(
    force=False
):
    if not force:
        cached = load_cached_result()

        if cached is not None:
            return cached

    try:
        sp500_history = (
            fetch_membership_history(
                SOURCE_FILES[
                    "SP500"
                ]
            )
        )

        nasdaq_history = (
            fetch_membership_history(
                SOURCE_FILES[
                    "NASDAQ100"
                ]
            )
        )

    except Exception as error:
        result = {
            "engine":
            ENGINE_VERSION,

            "validation_signature":
            VALIDATION_SIGNATURE,

            "status":
            "SOURCE_ERROR",

            "generated":
            datetime.now(
                timezone.utc
            ).isoformat(),

            "source_commit":
            SOURCE_COMMIT,

            "error":
            str(
                error
            )
        }

        save_result(
            result
        )

        return result

    sp500_unique = (
        unique_members_during_test(
            sp500_history
        )
    )

    nasdaq_unique = (
        unique_members_during_test(
            nasdaq_history
        )
    )

    tickers = sorted(
        set(
            sp500_unique
            +
            nasdaq_unique
            +
            [
                "SPY",
                "QQQ"
            ]
        )
    )

    close_frame = (
        download_price_frame(
            tickers
        )
    )

    if (
        close_frame.empty
        or
        "SPY"
        not in close_frame.columns
        or
        "QQQ"
        not in close_frame.columns
    ):
        result = {
            "engine":
            ENGINE_VERSION,

            "validation_signature":
            VALIDATION_SIGNATURE,

            "status":
            "PRICE_DATA_ERROR",

            "generated":
            datetime.now(
                timezone.utc
            ).isoformat(),

            "source_commit":
            SOURCE_COMMIT,

            "requested_ticker_count":
            len(
                tickers
            ),

            "downloaded_ticker_count":
            len(
                close_frame.columns
            )
        }

        save_result(
            result
        )

        return result

    sp500_result = validate_index(
        "S&P 500",
        sp500_history,
        close_frame,
        "SPY"
    )

    nasdaq_result = validate_index(
        "Nasdaq-100",
        nasdaq_history,
        close_frame,
        "QQQ"
    )

    downloaded = set(
        close_frame.columns
    )

    requested = set(
        tickers
    )

    missing = sorted(
        requested
        -
        downloaded
    )

    completed = [
        item
        for item in [
            sp500_result,
            nasdaq_result
        ]
        if item.get(
            "status"
        )
        ==
        "COMPLETE"
    ]

    positive_rankings = sum(
        1
        for item in completed
        if item.get(
            "ranking_verdict"
        )
        ==
        "RANKING_ADDS_VALUE"
    )

    if (
        len(
            completed
        )
        ==
        2
        and
        positive_rankings
        ==
        2
    ):
        overall_verdict = (
            "NEUTRAL_UNIVERSE_RANKING_VALIDATED"
        )

    elif (
        len(
            completed
        )
        ==
        2
        and
        positive_rankings
        ==
        0
    ):
        overall_verdict = (
            "NEUTRAL_UNIVERSE_RANKING_NOT_VALIDATED"
        )

    else:
        overall_verdict = (
            "NEUTRAL_UNIVERSE_EVIDENCE_MIXED"
        )

    result = {
        "engine":
        ENGINE_VERSION,

        "validation_signature":
        VALIDATION_SIGNATURE,

        "status":
        "COMPLETE",

        "cache_status":
        "FRESH",

        "generated":
        datetime.now(
            timezone.utc
        ).isoformat(),

        "test_period": {
            "start":
            TEST_START,

            "end":
            TEST_END
        },

        "source": {
            "repository":
            SOURCE_REPOSITORY,

            "commit":
            SOURCE_COMMIT,

            "files":
            SOURCE_FILES,

            "source_commit_date":
            "2026-06-07",

            "test_end_before_source_commit":
            True
        },

        "universe_counts": {
            "sp500_unique_members_during_test":
            len(
                sp500_unique
            ),

            "nasdaq100_unique_members_during_test":
            len(
                nasdaq_unique
            ),

            "requested_unique_price_tickers":
            len(
                requested
            ),

            "downloaded_price_tickers":
            len(
                downloaded
            ),

            "missing_price_tickers":
            len(
                missing
            )
        },

        "missing_price_ticker_sample":
        missing[
            :50
        ],

        "sp500":
        sp500_result,

        "nasdaq100":
        nasdaq_result,

        "overall_verdict":
        overall_verdict,

        "methodology": {
            "rebalance":
            "Monthly, first benchmark trading day",

            "decision_timing":
            (
                "Membership and strategic features are evaluated using the "
                "prior trading session; trades execute at the next session close."
            ),

            "ranking":
            (
                "V7.9 strategic composite with historical catalyst and sector "
                "components held neutral at 50."
            ),

            "portfolio_size":
            TOP_N,

            "trading_friction_bps":
            TRADING_FRICTION_BPS,

            "membership":
            (
                "Latest point-in-time membership snapshot effective on or "
                "before the decision date."
            )
        },

        "limitations": [
            (
                "Yahoo Finance may have incomplete price history for delisted, "
                "renamed or acquired securities. Coverage is reported at every "
                "rebalance and remains a residual survivorship/data-availability "
                "risk."
            ),
            (
                "Historical fundamentals, analyst revisions, news, catalysts "
                "and sector-state snapshots are not reconstructed; the test "
                "validates the reconstructable strategic price/risk ranking only."
            ),
            (
                "The external membership source is pinned to a fixed Git commit "
                "and the test ends before that commit date for reproducibility."
            ),
            (
                "Forward-filled prices are used only for valuation of existing "
                "positions when a daily quote disappears; new purchases require "
                "an exact execution-date quote."
            )
        ]
    }

    save_result(
        result
    )

    return result
