"""
AURORA Simple Factor Challenger — independent pre-registered holdout test.

This engine implements exactly:
docs/research/simple_factor_challenger_preregistration_v1.md

Primary holdout: 2012-01-01 through 2021-12-31.
Discovery period 2022-2026 is intentionally not used for the primary verdict.

Research-only. No live policy changes. No broker execution.
"""

from datetime import datetime, timezone
import csv
import io
import json
import math
import os

import numpy as np
import pandas as pd
import requests
import yfinance as yf

from engines.strategic_market_engine import (
    pct_return,
    safe_float
)

from engines.walk_forward_backtest_engine import (
    calculate_equity_metrics
)


ENGINE_VERSION = "Simple Factor Challenger Holdout v1.0"
VALIDATION_SIGNATURE = "SFC-HOLDOUT-1.0"

PREREGISTRATION_FILE = (
    "docs/research/simple_factor_challenger_preregistration_v1.md"
)

OUTPUT_FILE = (
    "docs/simple_factor_challenger_validation.json"
)

SOURCE_REPOSITORY = "thuningxu/sp500nq100"
SOURCE_COMMIT = "1cc1de2770874293597a418b41b079e5337b260c"

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

TEST_START = "2012-01-01"
TEST_END = "2021-12-31"

DOWNLOAD_START = "2010-12-01"
DOWNLOAD_END = "2022-01-10"

TOP_N = 12
MIN_WARMUP_SESSIONS = 252
TRADING_FRICTION_BPS = 10.0
STARTING_CAPITAL = 100000.0
BATCH_SIZE = 60
REQUEST_TIMEOUT_SECONDS = 45

MIN_REBALANCE_OBSERVATIONS = 100
MIN_AVERAGE_COVERAGE_PCT = 85.0
MIN_MONTHLY_COVERAGE_PCT = 75.0


def normalize_symbol(value):
    value = str(
        value
        or
        ""
    ).strip().upper()

    if not value:
        return None

    return value.replace(
        ".",
        "-"
    )


def fetch_membership_history(filename):
    response = requests.get(
        SOURCE_BASE_URL
        +
        filename,
        timeout=REQUEST_TIMEOUT_SECONDS
    )

    response.raise_for_status()

    reader = csv.DictReader(
        io.StringIO(
            response.text
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

        tickers = sorted(
            set(
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
                if normalize_symbol(
                    item
                )
            )
        )

        if tickers:
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


def membership_on(
    history,
    date_value
):
    selected = None

    for row in history:
        if row[
            "date"
        ] <= date_value:
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


def unique_members_during_period(
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
        if start
        <=
        row[
            "date"
        ]
        <=
        end
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

        clean = (
            series
            .dropna()
            .astype(
                float
            )
        )

        return (
            clean
            if not clean.empty
            else None
        )

    except Exception:
        return None


def download_price_frame(
    tickers
):
    tickers = sorted(
        set(
            ticker
            for ticker in tickers
            if ticker
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

        if (
            data is None
            or
            data.empty
        ):
            continue

        for ticker in batch:
            series = extract_close_series(
                data,
                ticker,
                len(
                    batch
                )
            )

            if series is not None:
                close_data[
                    ticker
                ] = series

    if not close_data:
        return pd.DataFrame()

    return pd.DataFrame(
        close_data
    ).sort_index()


def first_trading_day_each_month(
    trading_index
):
    first_days = []

    seen = set()

    for date_value in trading_index:
        key = (
            date_value.year,
            date_value.month
        )

        if key in seen:
            continue

        seen.add(
            key
        )

        first_days.append(
            date_value
        )

    return first_days


def previous_trading_date(
    trading_index,
    date_value
):
    prior = [
        item
        for item in trading_index
        if item
        <
        date_value
    ]

    return (
        prior[
            -1
        ]
        if prior
        else None
    )


def exact_price(
    close_frame,
    ticker,
    date_value
):
    if ticker not in close_frame.columns:
        return None

    try:
        value = safe_float(
            close_frame.loc[
                date_value,
                ticker
            ],
            None
        )
    except Exception:
        return None

    if (
        value is None
        or
        pd.isna(
            value
        )
        or
        value
        <=
        0
    ):
        return None

    return value


def factor_state(
    ticker,
    decision_date,
    close_frame,
    benchmark_ticker
):
    if (
        ticker
        not in close_frame.columns
        or
        benchmark_ticker
        not in close_frame.columns
    ):
        return None

    stock = (
        close_frame[
            ticker
        ].loc[
            :decision_date
        ].dropna()
    )

    benchmark = (
        close_frame[
            benchmark_ticker
        ].loc[
            :decision_date
        ].dropna()
    )

    if (
        len(
            stock
        )
        <=
        MIN_WARMUP_SESSIONS
        or
        len(
            benchmark
        )
        <=
        126
    ):
        return None

    return_12m = pct_return(
        stock,
        252
    )

    return_6m = pct_return(
        stock,
        126
    )

    benchmark_6m = pct_return(
        benchmark,
        126
    )

    if (
        return_12m is None
        or
        return_6m is None
        or
        benchmark_6m is None
    ):
        return None

    return {
        "ticker":
        ticker,

        "return_12m_pct":
        safe_float(
            return_12m,
            None
        ),

        "relative_strength_6m_pct":
        safe_float(
            return_6m,
            0.0
        )
        -
        safe_float(
            benchmark_6m,
            0.0
        )
    }


def percentile_scores(
    values
):
    if not values:
        return []

    series = pd.Series(
        values,
        dtype=float
    )

    ranks = series.rank(
        method="average",
        ascending=True
    )

    count = len(
        series
    )

    if count <= 1:
        return [
            50.0
        ]

    return (
        (
            ranks
            -
            1.0
        )
        /
        (
            count
            -
            1.0
        )
        *
        100.0
    ).tolist()


def rank_universe(
    members,
    decision_date,
    execution_date,
    close_frame,
    benchmark_ticker
):
    rows = []

    for ticker in members:
        state = factor_state(
            ticker,
            decision_date,
            close_frame,
            benchmark_ticker
        )

        if not state:
            continue

        if exact_price(
            close_frame,
            ticker,
            execution_date
        ) is None:
            continue

        rows.append(
            state
        )

    if not rows:
        return []

    momentum_percentiles = percentile_scores(
        [
            item[
                "return_12m_pct"
            ]
            for item in rows
        ]
    )

    rs_percentiles = percentile_scores(
        [
            item[
                "relative_strength_6m_pct"
            ]
            for item in rows
        ]
    )

    for index, item in enumerate(
        rows
    ):
        momentum_pct = safe_float(
            momentum_percentiles[
                index
            ],
            0.0
        )

        rs_pct = safe_float(
            rs_percentiles[
                index
            ],
            0.0
        )

        item[
            "momentum_12m_percentile"
        ] = round(
            momentum_pct,
            4
        )

        item[
            "relative_strength_6m_percentile"
        ] = round(
            rs_pct,
            4
        )

        item[
            "challenger_score"
        ] = round(
            0.50
            *
            momentum_pct
            +
            0.50
            *
            rs_pct,
            4
        )

    rows.sort(
        key=lambda item: (
            -
            safe_float(
                item.get(
                    "challenger_score"
                ),
                -999.0
            ),
            -
            safe_float(
                item.get(
                    "momentum_12m_percentile"
                ),
                -999.0
            ),
            -
            safe_float(
                item.get(
                    "relative_strength_6m_percentile"
                ),
                -999.0
            ),
            str(
                item.get(
                    "ticker",
                    ""
                )
            )
        )
    )

    return rows


def target_weights(
    mode,
    ranked_rows
):
    if not ranked_rows:
        return {}

    if mode == "PIT_EQUAL_WEIGHT":
        weight = (
            1.0
            /
            len(
                ranked_rows
            )
        )

        return {
            item[
                "ticker"
            ]:
            weight
            for item in ranked_rows
        }

    if mode == "CHALLENGER_TOP12":
        selected = ranked_rows[
            :TOP_N
        ]

        if len(
            selected
        ) < TOP_N:
            return {}

        weight = (
            1.0
            /
            TOP_N
        )

        return {
            item[
                "ticker"
            ]:
            weight
            for item in selected
        }

    return {}


def calendar_year_returns(
    equity_series
):
    equity = (
        equity_series
        .dropna()
        .sort_index()
    )

    result = {}

    for year, group in equity.groupby(
        equity.index.year
    ):
        if len(
            group
        ) < 2:
            continue

        result[
            str(
                year
            )
        ] = round(
            (
                group.iloc[
                    -1
                ]
                /
                group.iloc[
                    0
                ]
                -
                1.0
            )
            *
            100,
            2
        )

    return result


def simulate_mode(
    history,
    close_frame,
    benchmark_ticker,
    mode
):
    benchmark = (
        close_frame[
            benchmark_ticker
        ].dropna()
    )

    start = pd.Timestamp(
        TEST_START
    )

    end = pd.Timestamp(
        TEST_END
    )

    trading_dates = [
        date_value
        for date_value in benchmark.index
        if start
        <=
        date_value
        <=
        end
    ]

    if len(
        trading_dates
    ) < 500:
        return None

    rebalance_dates = set(
        first_trading_day_each_month(
            trading_dates
        )
    )

    valuation_frame = (
        close_frame
        .ffill()
    )

    cash = STARTING_CAPITAL
    shares = {}

    total_costs = 0.0
    turnover_notional = 0.0

    equity_points = {}
    coverage_rows = []
    selection_rows = []

    rebalance_count = 0
    full_top12_rebalances = 0

    for date_value in trading_dates:
        current_value = cash

        for ticker, quantity in (
            shares.items()
        ):
            price = exact_price(
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

        if date_value in rebalance_dates:
            decision_date = previous_trading_date(
                benchmark.index,
                date_value
            )

            if decision_date is not None:
                members = membership_on(
                    history,
                    decision_date
                )

                ranked = rank_universe(
                    members,
                    decision_date,
                    date_value,
                    close_frame,
                    benchmark_ticker
                )

                coverage_pct = (
                    len(
                        ranked
                    )
                    /
                    len(
                        members
                    )
                    *
                    100.0
                    if members
                    else 0.0
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
                        ranked
                    ),

                    "coverage_pct":
                    round(
                        coverage_pct,
                        2
                    )
                })

                if len(
                    ranked
                ) >= TOP_N:
                    full_top12_rebalances += 1

                weights = target_weights(
                    mode,
                    ranked
                )

                if weights:
                    desired_shares = {}

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
                            price
                            <=
                            0
                        ):
                            continue

                        desired_shares[
                            ticker
                        ] = (
                            current_value
                            *
                            weight
                            /
                            price
                        )

                    trade_notional = 0.0

                    all_trade_tickers = set(
                        shares
                    ) | set(
                        desired_shares
                    )

                    for ticker in (
                        all_trade_tickers
                    ):
                        price = exact_price(
                            close_frame,
                            ticker,
                            date_value
                        )

                        if price is None:
                            price = exact_price(
                                valuation_frame,
                                ticker,
                                date_value
                            )

                        if price is None:
                            continue

                        old_quantity = safe_float(
                            shares.get(
                                ticker,
                                0.0
                            ),
                            0.0
                        )

                        new_quantity = safe_float(
                            desired_shares.get(
                                ticker,
                                0.0
                            ),
                            0.0
                        )

                        trade_notional += abs(
                            new_quantity
                            -
                            old_quantity
                        ) * price

                    trading_cost = (
                        trade_notional
                        *
                        TRADING_FRICTION_BPS
                        /
                        10000.0
                    )

                    total_costs += trading_cost
                    turnover_notional += trade_notional

                    holdings_value = 0.0

                    for ticker, quantity in (
                        desired_shares.items()
                    ):
                        price = exact_price(
                            close_frame,
                            ticker,
                            date_value
                        )

                        if price is None:
                            continue

                        holdings_value += (
                            quantity
                            *
                            price
                        )

                    cash = (
                        current_value
                        -
                        holdings_value
                        -
                        trading_cost
                    )

                    shares = desired_shares
                    rebalance_count += 1

                    if mode == "CHALLENGER_TOP12":
                        selection_rows.append({
                            "execution_date":
                            str(
                                date_value.date()
                            ),

                            "selected":
                            [
                                {
                                    "ticker":
                                    item.get(
                                        "ticker"
                                    ),

                                    "challenger_score":
                                    item.get(
                                        "challenger_score"
                                    ),

                                    "return_12m_pct":
                                    round(
                                        safe_float(
                                            item.get(
                                                "return_12m_pct"
                                            ),
                                            0.0
                                        ),
                                        2
                                    ),

                                    "relative_strength_6m_pct":
                                    round(
                                        safe_float(
                                            item.get(
                                                "relative_strength_6m_pct"
                                            ),
                                            0.0
                                        ),
                                        2
                                    )
                                }
                                for item in ranked[
                                    :TOP_N
                                ]
                            ]
                        })

        end_value = cash

        for ticker, quantity in (
            shares.items()
        ):
            price = exact_price(
                valuation_frame,
                ticker,
                date_value
            )

            if price is None:
                continue

            end_value += (
                quantity
                *
                price
            )

        equity_points[
            date_value
        ] = end_value

    equity = pd.Series(
        equity_points,
        dtype=float
    ).sort_index()

    performance = calculate_equity_metrics(
        equity,
        benchmark.reindex(
            equity.index
        ),
        total_costs,
        turnover_notional,
        STARTING_CAPITAL
    )

    coverage_values = [
        safe_float(
            row.get(
                "coverage_pct"
            ),
            0.0
        )
        for row in coverage_rows
    ]

    return {
        "mode":
        mode,

        "performance":
        performance,

        "rebalance_count":
        rebalance_count,

        "coverage": {
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
                else 0.0
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
                else 0.0
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
                else 0.0
            ),

            "full_top12_rebalances":
            full_top12_rebalances,

            "coverage_history":
            coverage_rows
        },

        "calendar_year_returns_pct":
        calendar_year_returns(
            equity
        ),

        "selection_samples":
        (
            selection_rows[
                -6:
            ]
            if mode
            ==
            "CHALLENGER_TOP12"
            else []
        ),

        "_equity":
        equity
    }


def forward_trading_date(
    trading_index,
    execution_date,
    sessions
):
    dates = list(
        trading_index
    )

    try:
        position = dates.index(
            execution_date
        )
    except ValueError:
        return None

    target = (
        position
        +
        sessions
    )

    if target >= len(
        dates
    ):
        return None

    return dates[
        target
    ]


def cross_sectional_diagnostics(
    history,
    close_frame,
    benchmark_ticker
):
    benchmark = (
        close_frame[
            benchmark_ticker
        ].dropna()
    )

    start = pd.Timestamp(
        TEST_START
    )

    end = pd.Timestamp(
        TEST_END
    )

    execution_dates = [
        date_value
        for date_value in first_trading_day_each_month(
            benchmark.index
        )
        if start
        <=
        date_value
        <=
        end
    ]

    monthly_rows = []

    for execution_date in execution_dates:
        decision_date = previous_trading_date(
            benchmark.index,
            execution_date
        )

        if decision_date is None:
            continue

        future_date = forward_trading_date(
            benchmark.index,
            execution_date,
            60
        )

        if future_date is None:
            continue

        members = membership_on(
            history,
            decision_date
        )

        ranked = rank_universe(
            members,
            decision_date,
            execution_date,
            close_frame,
            benchmark_ticker
        )

        if len(
            ranked
        ) < 25:
            continue

        benchmark_entry = exact_price(
            close_frame,
            benchmark_ticker,
            execution_date
        )

        benchmark_future = exact_price(
            close_frame,
            benchmark_ticker,
            future_date
        )

        if (
            benchmark_entry is None
            or
            benchmark_future is None
        ):
            continue

        benchmark_return = (
            benchmark_future
            /
            benchmark_entry
            -
            1.0
        ) * 100

        observations = []

        for item in ranked:
            ticker = item[
                "ticker"
            ]

            entry = exact_price(
                close_frame,
                ticker,
                execution_date
            )

            future = exact_price(
                close_frame,
                ticker,
                future_date
            )

            if (
                entry is None
                or
                future is None
            ):
                continue

            observations.append({
                "score":
                safe_float(
                    item.get(
                        "challenger_score"
                    ),
                    0.0
                ),

                "excess_return":
                (
                    future
                    /
                    entry
                    -
                    1.0
                )
                *
                100
                -
                benchmark_return
            })

        if len(
            observations
        ) < 25:
            continue

        frame = pd.DataFrame(
            observations
        )

        spearman = safe_float(
            frame[
                "score"
            ].rank(
                method="average"
            ).corr(
                frame[
                    "excess_return"
                ].rank(
                    method="average"
                ),
                method="pearson"
            ),
            None
        )

        frame = frame.sort_values(
            "score"
        ).reset_index(
            drop=True
        )

        count = len(
            frame
        )

        frame[
            "quintile"
        ] = [
            min(
                5,
                int(
                    index
                    *
                    5
                    /
                    count
                )
                +
                1
            )
            for index in range(
                count
            )
        ]

        quintile_means = (
            frame.groupby(
                "quintile"
            )[
                "excess_return"
            ].mean().to_dict()
        )

        monthly_rows.append({
            "spearman":
            spearman,

            "q1":
            safe_float(
                quintile_means.get(
                    1
                ),
                None
            ),

            "q5":
            safe_float(
                quintile_means.get(
                    5
                ),
                None
            ),

            "observations":
            count
        })

    if not monthly_rows:
        return {
            "months":
            0,

            "observations":
            0,

            "average_spearman":
            None,

            "average_60d_q5_minus_q1_excess_return_pct":
            None
        }

    spearman_values = [
        row[
            "spearman"
        ]
        for row in monthly_rows
        if row[
            "spearman"
        ]
        is not None
        and
        not pd.isna(
            row[
                "spearman"
            ]
        )
    ]

    spreads = [
        row[
            "q5"
        ]
        -
        row[
            "q1"
        ]
        for row in monthly_rows
        if (
            row[
                "q5"
            ]
            is not None
            and
            row[
                "q1"
            ]
            is not None
        )
    ]

    return {
        "months":
        len(
            monthly_rows
        ),

        "observations":
        sum(
            row[
                "observations"
            ]
            for row in monthly_rows
        ),

        "average_spearman":
        (
            round(
                sum(
                    spearman_values
                )
                /
                len(
                    spearman_values
                ),
                4
            )
            if spearman_values
            else None
        ),

        "average_60d_q5_minus_q1_excess_return_pct":
        (
            round(
                sum(
                    spreads
                )
                /
                len(
                    spreads
                ),
                3
            )
            if spreads
            else None
        )
    }


def strip_internal_fields(
    result
):
    if not result:
        return result

    cleaned = dict(
        result
    )

    cleaned.pop(
        "_equity",
        None
    )

    return cleaned


def validity_gate(
    challenger_result
):
    coverage = (
        challenger_result.get(
            "coverage",
            {}
        )
        or
        {}
    )

    checks = {
        "rebalance_observations": {
            "required":
            MIN_REBALANCE_OBSERVATIONS,

            "actual":
            coverage.get(
                "rebalance_observations"
            ),

            "passed":
            safe_float(
                coverage.get(
                    "rebalance_observations"
                ),
                0
            )
            >=
            MIN_REBALANCE_OBSERVATIONS
        },

        "average_coverage_pct": {
            "required":
            MIN_AVERAGE_COVERAGE_PCT,

            "actual":
            coverage.get(
                "average_coverage_pct"
            ),

            "passed":
            safe_float(
                coverage.get(
                    "average_coverage_pct"
                ),
                0.0
            )
            >=
            MIN_AVERAGE_COVERAGE_PCT
        },

        "minimum_coverage_pct": {
            "required":
            MIN_MONTHLY_COVERAGE_PCT,

            "actual":
            coverage.get(
                "minimum_coverage_pct"
            ),

            "passed":
            safe_float(
                coverage.get(
                    "minimum_coverage_pct"
                ),
                0.0
            )
            >=
            MIN_MONTHLY_COVERAGE_PCT
        },

        "top12_available_each_counted_rebalance": {
            "required":
            coverage.get(
                "rebalance_observations"
            ),

            "actual":
            coverage.get(
                "full_top12_rebalances"
            ),

            "passed":
            (
                coverage.get(
                    "rebalance_observations"
                )
                ==
                coverage.get(
                    "full_top12_rebalances"
                )
                and
                safe_float(
                    coverage.get(
                        "rebalance_observations"
                    ),
                    0
                )
                >
                0
            )
        }
    }

    return {
        "passed":
        all(
            item[
                "passed"
            ]
            is True
            for item in checks.values()
        ),

        "checks":
        checks
    }


def evaluate_index(
    label,
    history,
    close_frame,
    benchmark_ticker
):
    challenger = simulate_mode(
        history,
        close_frame,
        benchmark_ticker,
        "CHALLENGER_TOP12"
    )

    control = simulate_mode(
        history,
        close_frame,
        benchmark_ticker,
        "PIT_EQUAL_WEIGHT"
    )

    if (
        challenger is None
        or
        control is None
    ):
        return {
            "index":
            label,

            "status":
            "NO_VALID_SIMULATION"
        }

    validity = validity_gate(
        challenger
    )

    challenger_perf = (
        challenger.get(
            "performance",
            {}
        )
        or
        {}
    )

    control_perf = (
        control.get(
            "performance",
            {}
        )
        or
        {}
    )

    cagr_advantage = (
        safe_float(
            challenger_perf.get(
                "cagr_pct"
            ),
            0.0
        )
        -
        safe_float(
            control_perf.get(
                "cagr_pct"
            ),
            0.0
        )
    )

    sharpe_advantage = (
        safe_float(
            challenger_perf.get(
                "sharpe_ratio"
            ),
            0.0
        )
        -
        safe_float(
            control_perf.get(
                "sharpe_ratio"
            ),
            0.0
        )
    )

    if not validity[
        "passed"
    ]:
        verdict = (
            "INVALID_DATA_COVERAGE"
        )

    elif (
        cagr_advantage
        >
        0.0
        and
        sharpe_advantage
        >=
        0.0
    ):
        verdict = (
            "PASS"
        )

    else:
        verdict = (
            "FAIL"
        )

    return {
        "index":
        label,

        "status":
        "COMPLETE",

        "benchmark":
        benchmark_ticker,

        "verdict":
        verdict,

        "validity_gate":
        validity,

        "challenger":
        strip_internal_fields(
            challenger
        ),

        "pit_equal_weight_control":
        strip_internal_fields(
            control
        ),

        "comparison": {
            "cagr_advantage_pct_points":
            round(
                cagr_advantage,
                2
            ),

            "sharpe_advantage":
            round(
                sharpe_advantage,
                3
            )
        },

        "cross_sectional_diagnostics":
        cross_sectional_diagnostics(
            history,
            close_frame,
            benchmark_ticker
        )
    }


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


def run_simple_factor_challenger():
    try:
        sp500_history = fetch_membership_history(
            SOURCE_FILES[
                "SP500"
            ]
        )

        nasdaq_history = fetch_membership_history(
            SOURCE_FILES[
                "NASDAQ100"
            ]
        )

    except Exception as error:
        result = {
            "engine":
            ENGINE_VERSION,

            "validation_signature":
            VALIDATION_SIGNATURE,

            "status":
            "SOURCE_ERROR",

            "error":
            str(
                error
            )
        }

        save_result(
            result
        )

        return result

    sp500_unique = unique_members_during_period(
        sp500_history
    )

    nasdaq_unique = unique_members_during_period(
        nasdaq_history
    )

    requested = sorted(
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

    close_frame = download_price_frame(
        requested
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

            "requested_tickers":
            len(
                requested
            ),

            "downloaded_tickers":
            len(
                close_frame.columns
            )
        }

        save_result(
            result
        )

        return result

    sp500_result = evaluate_index(
        "S&P 500",
        sp500_history,
        close_frame,
        "SPY"
    )

    nasdaq_result = evaluate_index(
        "Nasdaq-100",
        nasdaq_history,
        close_frame,
        "QQQ"
    )

    index_results = [
        sp500_result,
        nasdaq_result
    ]

    verdicts = [
        item.get(
            "verdict"
        )
        for item in index_results
    ]

    if (
        "INVALID_DATA_COVERAGE"
        in verdicts
        or
        any(
            item.get(
                "status"
            )
            !=
            "COMPLETE"
            for item in index_results
        )
    ):
        overall_verdict = (
            "CHALLENGER_DATA_INSUFFICIENT"
        )

    elif verdicts.count(
        "PASS"
    ) == 2:
        overall_verdict = (
            "CHALLENGER_VALIDATED_GENERAL"
        )

    elif verdicts.count(
        "PASS"
    ) == 1:
        overall_verdict = (
            "CHALLENGER_UNIVERSE_SPECIFIC_ONLY"
        )

    else:
        overall_verdict = (
            "CHALLENGER_NOT_VALIDATED"
        )

    downloaded = set(
        close_frame.columns
    )

    missing = sorted(
        set(
            requested
        )
        -
        downloaded
    )

    result = {
        "engine":
        ENGINE_VERSION,

        "validation_signature":
        VALIDATION_SIGNATURE,

        "status":
        "COMPLETE",

        "generated":
        datetime.now(
            timezone.utc
        ).isoformat(),

        "preregistration":
        PREREGISTRATION_FILE,

        "preregistration_frozen_before_test":
        True,

        "primary_holdout_period": {
            "start":
            TEST_START,

            "end":
            TEST_END
        },

        "discovery_period": {
            "start":
            "2022-06-01",

            "end":
            "2026-06-05",

            "role":
            "SECONDARY_ONLY",

            "replay_status":
            "DEFERRED_UNTIL_AFTER_PRIMARY"
        },

        "source": {
            "repository":
            SOURCE_REPOSITORY,

            "commit":
            SOURCE_COMMIT,

            "files":
            SOURCE_FILES
        },

        "formula": {
            "momentum":
            "252-session return percentile",

            "relative_strength":
            (
                "126-session stock return minus benchmark 126-session "
                "return, percentile-ranked"
            ),

            "score":
            (
                "0.50 * momentum_12m_percentile + "
                "0.50 * relative_strength_6m_percentile"
            ),

            "portfolio_size":
            TOP_N,

            "rebalance":
            "MONTHLY",

            "risk_overlay":
            False,

            "trading_friction_bps":
            TRADING_FRICTION_BPS
        },

        "universe_counts": {
            "sp500_unique_members":
            len(
                sp500_unique
            ),

            "nasdaq100_unique_members":
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
            :75
        ],

        "sp500":
        sp500_result,

        "nasdaq100":
        nasdaq_result,

        "overall_verdict":
        overall_verdict,

        "decision_consequence": (
            "If CHALLENGER_NOT_VALIDATED, close the current price-only "
            "cross-sectional stock-ranking research line. Do not mine the "
            "same holdout for replacement factor combinations. AURORA remains "
            "a risk/discipline/monitoring system unless a materially new "
            "independently testable information source or hypothesis emerges."
        ),

        "live_system": {
            "live_policy_changed":
            False,

            "shadow_candidate_changed":
            False,

            "paper_order_submission_authorized":
            False,

            "live_execution_authorized":
            False
        },

        "limitations": [
            (
                "Yahoo Finance may have incomplete historical data for "
                "delisted, renamed or acquired securities."
            ),
            (
                "The test validates only the pre-registered price-only "
                "challenger, not AURORA news, fundamentals or catalysts."
            ),
            (
                "Taxes are not modeled."
            )
        ]
    }

    save_result(
        result
    )

    return result
