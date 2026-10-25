"""
V8.0 AURORA Historical Replay & Walk-Forward Backtest Engine

Purpose:
- Replay the reconstructable V7.9 strategic price/risk layer through history
- Use only information available before each simulated execution
- Compare the strategic de-risking overlay with SPY
- Measure CAGR, Sharpe, Sortino, max drawdown, hit rate, turnover and costs
- Produce sequential out-of-sample walk-forward folds

Scope:
- Current portfolio tickers are the validation universe.
- Historical news, catalyst and sector snapshots were not archived reliably,
  so they are NOT reconstructed or invented here.
- This is therefore a strategic price/risk-layer backtest, not a claim that
  the entire live AURORA pipeline has been historically reproduced.
- Current holdings create survivorship/selection bias; results must not be
  treated as production proof.

Execution model:
- Strategic features are calculated using data through the prior session.
- Target weights are executed at the next session close.
- Rebalance frequency: weekly (every 5 US trading sessions).
- Cash is allowed when the strategic overlay de-risks.
- Trading friction assumption: commission + slippage on traded notional.

No broker orders are sent.
"""

from datetime import datetime, timezone
import hashlib
import json
import math
import os

import numpy as np
import pandas as pd
import yfinance as yf

from engines.strategic_market_engine import (
    calculate_annualized_volatility,
    calculate_max_drawdown,
    calculate_sma,
    pct_return,
    score_risk,
    score_trend,
    safe_float
)


ENGINE_VERSION = (
    "V8.0 Historical Replay & Walk-Forward Backtest Engine"
)

BACKTEST_SIGNATURE = "V8.4.4"

OUTPUT_FILE = "docs/walk_forward_backtest.json"

STARTING_CAPITAL = 100000.0

LOOKBACK_PERIOD = "5y"

MIN_WARMUP_SESSIONS = 252

MIN_ELIGIBLE_RATIO = 0.50

REBALANCE_EVERY_SESSIONS = 5

WALK_FORWARD_FOLD_SESSIONS = 126

COMMISSION_BPS = 5.0

SLIPPAGE_BPS = 5.0

TOTAL_TRADING_FRICTION_BPS = (
    COMMISSION_BPS
    +
    SLIPPAGE_BPS
)

SIGNAL_EVALUATION_SESSIONS = 20

ROLLING_OOS_LOOKBACK_SESSIONS = 126

ROLLING_OOS_REBALANCE_SESSIONS = 21


def portfolio_signature(tickers):
    raw = "|".join(
        sorted(
            set(
                tickers
            )
        )
    )

    return hashlib.sha1(
        raw.encode(
            "utf-8"
        )
    ).hexdigest()[:16]


def load_cached_result(
    signature,
    market_date
):
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
                "backtest_signature"
            )
            !=
            BACKTEST_SIGNATURE
        ):
            return None

        if (
            data.get(
                "portfolio_signature"
            )
            !=
            signature
        ):
            return None

        if (
            data.get(
                "market_date"
            )
            !=
            market_date
        ):
            return None

        data[
            "cache_status"
        ] = "REUSED"

        return data

    except Exception:
        return None


def save_result(data):
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
            data,
            file,
            indent=2,
            ensure_ascii=False
        )


def extract_close_frame(
    data,
    tickers
):
    close_data = {}

    for ticker in tickers:
        try:
            if isinstance(
                data.columns,
                pd.MultiIndex
            ):
                level_zero = list(
                    data.columns.get_level_values(
                        0
                    )
                )

                level_one = list(
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
                    continue

            else:
                if (
                    len(
                        tickers
                    )
                    !=
                    1
                    or
                    "Close"
                    not in data.columns
                ):
                    continue

                series = data[
                    "Close"
                ]

            clean = series.dropna()

            if clean.empty:
                continue

            close_data[
                ticker
            ] = clean.astype(
                float
            )

        except Exception:
            continue

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


def download_close_history(
    tickers
):
    tickers = list(
        dict.fromkeys(
            tickers
        )
    )

    try:
        data = yf.download(
            tickers=tickers,
            period=LOOKBACK_PERIOD,
            interval="1d",
            auto_adjust=True,
            progress=False,
            threads=True,
            group_by="ticker"
        )

    except Exception:
        return pd.DataFrame()

    if data is None or data.empty:
        return pd.DataFrame()

    return extract_close_frame(
        data,
        tickers
    )


def eligible_tickers_at_date(
    close_frame,
    tickers,
    date_value
):
    eligible = []

    for ticker in tickers:
        if ticker not in close_frame.columns:
            continue

        history = close_frame[
            ticker
        ].loc[
            :date_value
        ].dropna()

        if len(
            history
        ) >= MIN_WARMUP_SESSIONS:
            eligible.append(
                ticker
            )

    return eligible


def find_start_date(
    close_frame,
    tickers
):
    if (
        close_frame.empty
        or
        "SPY"
        not in close_frame.columns
    ):
        return None

    spy_dates = (
        close_frame[
            "SPY"
        ].dropna().index
    )

    min_eligible = max(
        3,
        math.ceil(
            len(
                tickers
            )
            *
            MIN_ELIGIBLE_RATIO
        )
    )

    for date_value in spy_dates[
        MIN_WARMUP_SESSIONS:
    ]:
        eligible = (
            eligible_tickers_at_date(
                close_frame,
                tickers,
                date_value
            )
        )

        if len(
            eligible
        ) >= min_eligible:
            return date_value

    return None


def strategic_state_as_of(
    ticker,
    decision_date,
    close_frame
):
    if (
        ticker
        not in close_frame.columns
        or
        "SPY"
        not in close_frame.columns
    ):
        return None

    close = close_frame[
        ticker
    ].loc[
        :decision_date
    ].dropna()

    spy_close = close_frame[
        "SPY"
    ].loc[
        :decision_date
    ].dropna()

    if len(
        close
    ) < MIN_WARMUP_SESSIONS:
        return None

    last_price = safe_float(
        close.iloc[-1]
    )

    return_3m = pct_return(
        close,
        63
    )

    return_6m = pct_return(
        close,
        126
    )

    return_12m = pct_return(
        close,
        252
    )

    spy_3m = (
        pct_return(
            spy_close,
            63
        )
        if len(
            spy_close
        ) > 63
        else None
    )

    spy_6m = (
        pct_return(
            spy_close,
            126
        )
        if len(
            spy_close
        ) > 126
        else None
    )

    rs_3m = (
        return_3m
        -
        spy_3m
        if (
            return_3m is not None
            and
            spy_3m is not None
        )
        else None
    )

    rs_6m = (
        return_6m
        -
        spy_6m
        if (
            return_6m is not None
            and
            spy_6m is not None
        )
        else None
    )

    sma50 = calculate_sma(
        close,
        50
    )

    sma100 = calculate_sma(
        close,
        100
    )

    sma200 = calculate_sma(
        close,
        200
    )

    max_drawdown_6m = (
        calculate_max_drawdown(
            close,
            126
        )
    )

    max_drawdown_12m = (
        calculate_max_drawdown(
            close,
            252
        )
    )

    volatility_60d = (
        calculate_annualized_volatility(
            close,
            60
        )
    )

    trend_score = score_trend(
        last_price=last_price,
        sma50=sma50,
        sma100=sma100,
        sma200=sma200,
        return_3m=return_3m,
        return_6m=return_6m,
        return_12m=return_12m,
        rs_3m=rs_3m,
        rs_6m=rs_6m
    )

    risk_score = score_risk(
        max_drawdown_6m,
        max_drawdown_12m,
        volatility_60d
    )

    above_sma200 = (
        last_price > sma200
        if sma200 is not None
        else None
    )

    return {
        "ticker":
        ticker,

        "date":
        str(
            decision_date.date()
        ),

        "price":
        last_price,

        "trend_score":
        trend_score,

        "risk_score":
        risk_score,

        "return_3m_pct":
        return_3m,

        "return_6m_pct":
        return_6m,

        "return_12m_pct":
        return_12m,

        "relative_strength_3m_pct":
        rs_3m,

        "relative_strength_6m_pct":
        rs_6m,

        "above_sma200":
        above_sma200,

        "sma200":
        sma200
    }


def replay_action(
    state
):
    if not state:
        return "NO_DATA"

    trend_score = safe_float(
        state.get(
            "trend_score",
            50
        )
    )

    risk_score = safe_float(
        state.get(
            "risk_score",
            50
        )
    )

    return_6m = safe_float(
        state.get(
            "return_6m_pct",
            0
        )
    )

    rs_6m = safe_float(
        state.get(
            "relative_strength_6m_pct",
            0
        )
    )

    above_sma200 = state.get(
        "above_sma200"
    )

    severe_trend_break = (
        trend_score < 30
        and
        above_sma200 is False
        and
        return_6m <= -20
        and
        rs_6m <= -15
    )

    severe_risk_break = (
        risk_score < 35
        and
        above_sma200 is False
        and
        return_6m < 0
    )

    if (
        severe_trend_break
        or
        severe_risk_break
    ):
        return "EXIT"

    if (
        trend_score < 40
        and
        above_sma200 is False
        and
        return_6m < -8
        and
        rs_6m < -8
    ):
        return "REDUCE"

    if (
        trend_score >= 65
        and
        risk_score >= 45
        and
        above_sma200 is True
        and
        return_6m > 0
        and
        rs_6m > 0
    ):
        return "HOLD"

    if (
        above_sma200 is True
        or
        return_6m > 0
        or
        rs_6m > 0
    ):
        return "WATCH"

    return "WATCH"


def exposure_multiplier(
    action
):
    return {
        "HOLD": 1.00,
        "WATCH": 0.75,
        "REDUCE": 0.50,
        "EXIT": 0.00
    }.get(
        action,
        0.0
    )


def build_target_weights(
    decision_date,
    tickers,
    close_frame
):
    eligible = (
        eligible_tickers_at_date(
            close_frame,
            tickers,
            decision_date
        )
    )

    if not eligible:
        return (
            {},
            {}
        )

    base_weight = (
        1.0
        /
        len(
            eligible
        )
    )

    weights = {}

    states = {}

    for ticker in eligible:
        state = strategic_state_as_of(
            ticker,
            decision_date,
            close_frame
        )

        if not state:
            continue

        action = replay_action(
            state
        )

        states[
            ticker
        ] = {
            **state,
            "action":
            action,

            "exposure_multiplier":
            exposure_multiplier(
                action
            )
        }

        weights[
            ticker
        ] = (
            base_weight
            *
            exposure_multiplier(
                action
            )
        )

    total_weight = sum(
        weights.values()
    )

    if total_weight > 1:
        scale = (
            1
            /
            total_weight
        )

        weights = {
            ticker:
            weight
            *
            scale
            for ticker, weight in (
                weights.items()
            )
        }

    return (
        weights,
        states
    )


def calculate_equity_metrics(
    equity_series,
    spy_series,
    total_trading_costs,
    turnover_notional,
    starting_capital
):
    equity = equity_series.dropna()

    spy = spy_series.dropna()

    if len(
        equity
    ) < 2:
        return {}

    returns = (
        equity
        .pct_change()
        .dropna()
    )

    years = (
        len(
            returns
        )
        /
        252
    )

    total_return = (
        equity.iloc[-1]
        /
        equity.iloc[0]
        -
        1
    )

    cagr = (
        (
            equity.iloc[-1]
            /
            equity.iloc[0]
        )
        **
        (
            1
            /
            years
        )
        -
        1
        if years > 0
        else 0
    )

    volatility = (
        safe_float(
            returns.std()
        )
        *
        math.sqrt(
            252
        )
    )

    sharpe = (
        safe_float(
            returns.mean()
        )
        /
        safe_float(
            returns.std()
        )
        *
        math.sqrt(
            252
        )
        if safe_float(
            returns.std()
        ) > 0
        else 0
    )

    downside = returns[
        returns < 0
    ]

    downside_std = safe_float(
        downside.std()
    )

    sortino = (
        safe_float(
            returns.mean()
        )
        /
        downside_std
        *
        math.sqrt(
            252
        )
        if downside_std > 0
        else 0
    )

    running_max = equity.cummax()

    drawdown = (
        equity
        /
        running_max
        -
        1
    )

    max_drawdown = abs(
        safe_float(
            drawdown.min()
        )
    )

    calmar = (
        cagr
        /
        max_drawdown
        if max_drawdown > 0
        else 0
    )

    positive_sum = safe_float(
        returns[
            returns > 0
        ].sum()
    )

    negative_sum = abs(
        safe_float(
            returns[
                returns < 0
            ].sum()
        )
    )

    profit_factor = (
        positive_sum
        /
        negative_sum
        if negative_sum > 0
        else None
    )

    aligned_spy = (
        spy.reindex(
            equity.index
        ).dropna()
    )

    spy_total_return = None

    spy_cagr = None

    if len(
        aligned_spy
    ) >= 2:
        spy_total_return = (
            aligned_spy.iloc[-1]
            /
            aligned_spy.iloc[0]
            -
            1
        )

        spy_years = (
            len(
                aligned_spy
            )
            -
            1
        ) / 252

        if spy_years > 0:
            spy_cagr = (
                (
                    aligned_spy.iloc[-1]
                    /
                    aligned_spy.iloc[0]
                )
                **
                (
                    1
                    /
                    spy_years
                )
                -
                1
            )

    annualized_turnover = (
        turnover_notional
        /
        starting_capital
        /
        years
        if years > 0
        else 0
    )

    return {
        "starting_value":
        round(
            safe_float(
                equity.iloc[0]
            ),
            2
        ),

        "ending_value":
        round(
            safe_float(
                equity.iloc[-1]
            ),
            2
        ),

        "total_return_pct":
        round(
            total_return
            *
            100,
            2
        ),

        "cagr_pct":
        round(
            cagr
            *
            100,
            2
        ),

        "annualized_volatility_pct":
        round(
            volatility
            *
            100,
            2
        ),

        "sharpe_ratio":
        round(
            sharpe,
            3
        ),

        "sortino_ratio":
        round(
            sortino,
            3
        ),

        "max_drawdown_pct":
        round(
            max_drawdown
            *
            100,
            2
        ),

        "calmar_ratio":
        round(
            calmar,
            3
        ),

        "profit_factor_daily":
        (
            round(
                profit_factor,
                3
            )
            if profit_factor is not None
            else None
        ),

        "spy_total_return_pct":
        (
            round(
                spy_total_return
                *
                100,
                2
            )
            if spy_total_return is not None
            else None
        ),

        "spy_cagr_pct":
        (
            round(
                spy_cagr
                *
                100,
                2
            )
            if spy_cagr is not None
            else None
        ),

        "cagr_alpha_vs_spy_pct":
        (
            round(
                (
                    cagr
                    -
                    spy_cagr
                )
                *
                100,
                2
            )
            if spy_cagr is not None
            else None
        ),

        "total_trading_costs":
        round(
            total_trading_costs,
            2
        ),

        "trading_cost_pct_of_starting_capital":
        round(
            total_trading_costs
            /
            starting_capital
            *
            100,
            3
        ),

        "annualized_turnover_x":
        round(
            annualized_turnover,
            2
        ),

        "trading_days":
        len(
            returns
        ),

        "years":
        round(
            years,
            2
        )
    }


def evaluate_action_changes(
    signal_events,
    close_frame
):
    evaluated = []

    spy = close_frame[
        "SPY"
    ].dropna()

    spy_dates = list(
        spy.index
    )

    for event in signal_events:
        ticker = event.get(
            "ticker"
        )

        signal_date = event.get(
            "decision_date"
        )

        action = event.get(
            "action"
        )

        if (
            ticker not in close_frame.columns
            or
            signal_date is None
        ):
            continue

        try:
            date_index = spy_dates.index(
                signal_date
            )
        except ValueError:
            continue

        target_index = (
            date_index
            +
            SIGNAL_EVALUATION_SESSIONS
        )

        if target_index >= len(
            spy_dates
        ):
            continue

        future_date = spy_dates[
            target_index
        ]

        stock_series = close_frame[
            ticker
        ].dropna()

        try:
            entry_price = safe_float(
                stock_series.loc[
                    signal_date
                ]
            )

            future_price = safe_float(
                stock_series.loc[
                    future_date
                ]
            )

            spy_entry = safe_float(
                spy.loc[
                    signal_date
                ]
            )

            spy_future = safe_float(
                spy.loc[
                    future_date
                ]
            )

        except Exception:
            continue

        if min(
            entry_price,
            future_price,
            spy_entry,
            spy_future
        ) <= 0:
            continue

        stock_return = (
            future_price
            /
            entry_price
            -
            1
        ) * 100

        spy_return = (
            spy_future
            /
            spy_entry
            -
            1
        ) * 100

        excess = (
            stock_return
            -
            spy_return
        )

        defensive = action in [
            "REDUCE",
            "EXIT"
        ]

        decision_alpha = (
            -excess
            if defensive
            else excess
        )

        execution_date = event.get(
            "execution_date"
        )

        evaluated.append({
            **event,

            "decision_date":
            str(
                signal_date.date()
            ),

            "execution_date":
            (
                str(
                    execution_date.date()
                )
                if hasattr(
                    execution_date,
                    "date"
                )
                else str(
                    execution_date
                )
                if execution_date is not None
                else None
            ),

            "evaluation_date":
            str(
                future_date.date()
            ),

            "stock_return_20d_pct":
            round(
                stock_return,
                2
            ),

            "spy_return_20d_pct":
            round(
                spy_return,
                2
            ),

            "decision_alpha_20d_pct":
            round(
                decision_alpha,
                2
            ),

            "hit":
            decision_alpha > 0
        })

    if not evaluated:
        return {
            "evaluated_signal_changes":
            0,

            "hit_rate_pct":
            None,

            "average_decision_alpha_20d_pct":
            None,

            "events":
            []
        }

    hits = sum(
        1
        for item in evaluated
        if item.get(
            "hit"
        )
    )

    avg_alpha = (
        sum(
            safe_float(
                item.get(
                    "decision_alpha_20d_pct"
                )
            )
            for item in evaluated
        )
        /
        len(
            evaluated
        )
    )

    def summarize_events(
        items
    ):
        if not items:
            return {
                "evaluated":
                0,

                "hit_rate_pct":
                None,

                "average_decision_alpha_20d_pct":
                None
            }

        item_hits = sum(
            1
            for item in items
            if item.get(
                "hit"
            )
        )

        item_alpha = (
            sum(
                safe_float(
                    item.get(
                        "decision_alpha_20d_pct"
                    )
                )
                for item in items
            )
            /
            len(
                items
            )
        )

        return {
            "evaluated":
            len(
                items
            ),

            "hit_rate_pct":
            round(
                item_hits
                /
                len(
                    items
                )
                *
                100,
                1
            ),

            "average_decision_alpha_20d_pct":
            round(
                item_alpha,
                2
            )
        }

    actions = sorted(
        set(
            item.get(
                "action"
            )
            for item in evaluated
            if item.get(
                "action"
            )
        )
    )

    by_action = {
        action:
        summarize_events([
            item
            for item in evaluated
            if item.get(
                "action"
            )
            ==
            action
        ])
        for action in actions
    }

    defensive_events = [
        item
        for item in evaluated
        if item.get(
            "action"
        )
        in [
            "REDUCE",
            "EXIT"
        ]
    ]

    return {
        "evaluated_signal_changes":
        len(
            evaluated
        ),

        "hit_rate_pct":
        round(
            hits
            /
            len(
                evaluated
            )
            *
            100,
            1
        ),

        "average_decision_alpha_20d_pct":
        round(
            avg_alpha,
            2
        ),

        "by_action":
        by_action,

        "defensive_reduce_exit":
        summarize_events(
            defensive_events
        ),

        "events":
        evaluated[-50:]
    }


def build_walk_forward_folds(
    equity_series,
    spy_price_series
):
    equity = equity_series.dropna()

    if len(
        equity
    ) < 2:
        return []

    dates = list(
        equity.index
    )

    folds = []

    start = 0

    fold_number = 1

    while (
        start
        <
        len(
            dates
        )
        -
        1
    ):
        end = min(
            start
            +
            WALK_FORWARD_FOLD_SESSIONS,
            len(
                dates
            )
            -
            1
        )

        if (
            end
            -
            start
        ) < 40:
            break

        start_date = dates[
            start
        ]

        end_date = dates[
            end
        ]

        start_value = safe_float(
            equity.loc[
                start_date
            ]
        )

        end_value = safe_float(
            equity.loc[
                end_date
            ]
        )

        strategy_return = (
            end_value
            /
            start_value
            -
            1
        ) * 100

        spy_slice = (
            spy_price_series.reindex(
                equity.loc[
                    start_date:
                    end_date
                ].index
            ).dropna()
        )

        spy_return = None

        if len(
            spy_slice
        ) >= 2:
            spy_return = (
                safe_float(
                    spy_slice.iloc[-1]
                )
                /
                safe_float(
                    spy_slice.iloc[0]
                )
                -
                1
            ) * 100

        fold_equity = equity.loc[
            start_date:
            end_date
        ]

        fold_drawdown = (
            fold_equity
            /
            fold_equity.cummax()
            -
            1
        )

        max_drawdown = abs(
            safe_float(
                fold_drawdown.min()
            )
        ) * 100

        folds.append({
            "fold":
            fold_number,

            "start_date":
            str(
                start_date.date()
            ),

            "end_date":
            str(
                end_date.date()
            ),

            "trading_sessions":
            end
            -
            start,

            "strategy_return_pct":
            round(
                strategy_return,
                2
            ),

            "spy_return_pct":
            (
                round(
                    spy_return,
                    2
                )
                if spy_return is not None
                else None
            ),

            "excess_return_pct":
            (
                round(
                    strategy_return
                    -
                    spy_return,
                    2
                )
                if spy_return is not None
                else None
            ),

            "max_drawdown_pct":
            round(
                max_drawdown,
                2
            ),

            "out_of_sample":
            True
        })

        start = end

        fold_number += 1

    return folds


def simulate_strategy(
    close_frame,
    tickers,
    start_date
):
    spy = close_frame[
        "SPY"
    ].dropna()

    trading_dates = [
        date_value
        for date_value in spy.index
        if date_value >= start_date
    ]

    if len(
        trading_dates
    ) < 50:
        return None

    capital = STARTING_CAPITAL

    cash = STARTING_CAPITAL

    shares = {
        ticker:
        0.0
        for ticker in tickers
    }

    total_trading_costs = 0.0

    turnover_notional = 0.0

    equity_points = {}

    signal_events = []

    last_actions = {}

    rebalance_count = 0

    for index, date_value in enumerate(
        trading_dates
    ):
        prices_today = {}

        for ticker in tickers:
            if ticker not in close_frame.columns:
                continue

            try:
                price = safe_float(
                    close_frame.loc[
                        date_value,
                        ticker
                    ],
                    None
                )

                if (
                    price is not None
                    and
                    not pd.isna(
                        price
                    )
                    and
                    price > 0
                ):
                    prices_today[
                        ticker
                    ] = price

            except Exception:
                continue

        position_value = sum(
            shares.get(
                ticker,
                0
            )
            *
            prices_today.get(
                ticker,
                0
            )
            for ticker in tickers
        )

        capital = (
            cash
            +
            position_value
        )

        should_rebalance = (
            index == 0
            or
            index
            %
            REBALANCE_EVERY_SESSIONS
            ==
            0
        )

        if (
            should_rebalance
            and
            index > 0
        ):
            decision_date = trading_dates[
                index - 1
            ]

            target_weights, states = (
                build_target_weights(
                    decision_date,
                    tickers,
                    close_frame
                )
            )

            if target_weights:
                rebalance_count += 1

                for ticker, state in (
                    states.items()
                ):
                    action = state.get(
                        "action"
                    )

                    previous_action = (
                        last_actions.get(
                            ticker
                        )
                    )

                    if (
                        action
                        !=
                        previous_action
                    ):
                        signal_events.append({
                            "ticker":
                            ticker,

                            "decision_date":
                            decision_date,

                            "execution_date":
                            date_value,

                            "action":
                            action,

                            "previous_action":
                            previous_action,

                            "trend_score":
                            state.get(
                                "trend_score"
                            ),

                            "risk_score":
                            state.get(
                                "risk_score"
                            ),

                            "return_6m_pct":
                            state.get(
                                "return_6m_pct"
                            ),

                            "relative_strength_6m_pct":
                            state.get(
                                "relative_strength_6m_pct"
                            )
                        })

                    last_actions[
                        ticker
                    ] = action

                pre_trade_value = capital

                target_values = {
                    ticker:
                    pre_trade_value
                    *
                    weight
                    for ticker, weight in (
                        target_weights.items()
                    )
                }

                traded_notional = 0.0

                for ticker in tickers:
                    price = prices_today.get(
                        ticker
                    )

                    if (
                        price is None
                        or
                        price <= 0
                    ):
                        continue

                    current_value = (
                        shares.get(
                            ticker,
                            0
                        )
                        *
                        price
                    )

                    target_value = target_values.get(
                        ticker,
                        0.0
                    )

                    trade_value = (
                        target_value
                        -
                        current_value
                    )

                    traded_notional += abs(
                        trade_value
                    )

                trading_cost = (
                    traded_notional
                    *
                    TOTAL_TRADING_FRICTION_BPS
                    /
                    10000
                )

                post_cost_value = max(
                    0,
                    pre_trade_value
                    -
                    trading_cost
                )

                target_values = {
                    ticker:
                    post_cost_value
                    *
                    weight
                    for ticker, weight in (
                        target_weights.items()
                    )
                }

                new_shares = {
                    ticker:
                    0.0
                    for ticker in tickers
                }

                invested_value = 0.0

                for ticker, target_value in (
                    target_values.items()
                ):
                    price = prices_today.get(
                        ticker
                    )

                    if (
                        price is None
                        or
                        price <= 0
                    ):
                        continue

                    ticker_shares = (
                        target_value
                        /
                        price
                    )

                    new_shares[
                        ticker
                    ] = ticker_shares

                    invested_value += target_value

                shares = new_shares

                cash = max(
                    0,
                    post_cost_value
                    -
                    invested_value
                )

                total_trading_costs += (
                    trading_cost
                )

                turnover_notional += (
                    traded_notional
                )

                capital = post_cost_value

        position_value = sum(
            shares.get(
                ticker,
                0
            )
            *
            prices_today.get(
                ticker,
                0
            )
            for ticker in tickers
        )

        capital = (
            cash
            +
            position_value
        )

        equity_points[
            date_value
        ] = capital

    equity_series = pd.Series(
        equity_points
    ).sort_index()

    spy_start = safe_float(
        spy.loc[
            trading_dates[0]
        ]
    )

    spy_equity = (
        spy.reindex(
            equity_series.index
        )
        /
        spy_start
        *
        STARTING_CAPITAL
    )

    metrics = calculate_equity_metrics(
        equity_series,
        spy_equity,
        total_trading_costs,
        turnover_notional,
        STARTING_CAPITAL
    )

    signal_validation = (
        evaluate_action_changes(
            signal_events,
            close_frame
        )
    )

    folds = build_walk_forward_folds(
        equity_series,
        spy
    )

    return {
        "equity_series":
        equity_series,

        "spy_equity":
        spy_equity,

        "metrics":
        metrics,

        "signal_validation":
        signal_validation,

        "walk_forward_folds":
        folds,

        "rebalance_count":
        rebalance_count,

        "signal_change_count":
        len(
            signal_events
        ),

        "last_actions":
        last_actions
    }


def simulate_equal_weight_control(
    close_frame,
    tickers,
    start_date
):
    """
    Same-universe control portfolio.

    Uses the exact same:
    - current ticker universe
    - historical eligibility rules
    - weekly rebalance timing
    - next-session execution convention
    - commission/slippage assumptions

    Difference:
    - no strategic de-risking overlay
    - 100% equal-weight across eligible names

    This isolates whether the strategic overlay itself adds value beyond
    simply owning the selected current portfolio names.
    """

    spy = close_frame[
        "SPY"
    ].dropna()

    trading_dates = [
        date_value
        for date_value in spy.index
        if date_value >= start_date
    ]

    if len(
        trading_dates
    ) < 50:
        return None

    capital = STARTING_CAPITAL

    cash = STARTING_CAPITAL

    shares = {
        ticker:
        0.0
        for ticker in tickers
    }

    total_trading_costs = 0.0

    turnover_notional = 0.0

    equity_points = {}

    rebalance_count = 0

    for index, date_value in enumerate(
        trading_dates
    ):
        prices_today = {}

        for ticker in tickers:
            if ticker not in close_frame.columns:
                continue

            try:
                series = close_frame[
                    ticker
                ].loc[
                    :date_value
                ].dropna()

                if series.empty:
                    continue

                price = safe_float(
                    series.iloc[-1],
                    None
                )

                if (
                    price is not None
                    and
                    price > 0
                ):
                    prices_today[
                        ticker
                    ] = price

            except Exception:
                continue

        position_value = sum(
            shares.get(
                ticker,
                0
            )
            *
            prices_today.get(
                ticker,
                0
            )
            for ticker in tickers
        )

        capital = (
            cash
            +
            position_value
        )

        should_rebalance = (
            index > 0
            and
            index
            %
            REBALANCE_EVERY_SESSIONS
            ==
            0
        )

        if should_rebalance:
            decision_date = trading_dates[
                index - 1
            ]

            eligible = (
                eligible_tickers_at_date(
                    close_frame,
                    tickers,
                    decision_date
                )
            )

            if eligible:
                rebalance_count += 1

                base_weight = (
                    1.0
                    /
                    len(
                        eligible
                    )
                )

                target_weights = {
                    ticker:
                    base_weight
                    for ticker in eligible
                }

                pre_trade_value = capital

                target_values = {
                    ticker:
                    pre_trade_value
                    *
                    weight
                    for ticker, weight in (
                        target_weights.items()
                    )
                }

                traded_notional = 0.0

                for ticker in tickers:
                    price = prices_today.get(
                        ticker
                    )

                    if (
                        price is None
                        or
                        price <= 0
                    ):
                        continue

                    current_value = (
                        shares.get(
                            ticker,
                            0
                        )
                        *
                        price
                    )

                    target_value = target_values.get(
                        ticker,
                        0.0
                    )

                    traded_notional += abs(
                        target_value
                        -
                        current_value
                    )

                trading_cost = (
                    traded_notional
                    *
                    TOTAL_TRADING_FRICTION_BPS
                    /
                    10000
                )

                post_cost_value = max(
                    0,
                    pre_trade_value
                    -
                    trading_cost
                )

                new_shares = {
                    ticker:
                    0.0
                    for ticker in tickers
                }

                invested_value = 0.0

                for ticker, weight in (
                    target_weights.items()
                ):
                    price = prices_today.get(
                        ticker
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

                    new_shares[
                        ticker
                    ] = (
                        target_value
                        /
                        price
                    )

                    invested_value += (
                        target_value
                    )

                shares = new_shares

                cash = max(
                    0,
                    post_cost_value
                    -
                    invested_value
                )

                total_trading_costs += (
                    trading_cost
                )

                turnover_notional += (
                    traded_notional
                )

                capital = post_cost_value

        position_value = sum(
            shares.get(
                ticker,
                0
            )
            *
            prices_today.get(
                ticker,
                0
            )
            for ticker in tickers
        )

        capital = (
            cash
            +
            position_value
        )

        equity_points[
            date_value
        ] = capital

    equity_series = pd.Series(
        equity_points
    ).sort_index()

    spy_start = safe_float(
        spy.loc[
            trading_dates[0]
        ]
    )

    spy_equity = (
        spy.reindex(
            equity_series.index
        )
        /
        spy_start
        *
        STARTING_CAPITAL
    )

    metrics = calculate_equity_metrics(
        equity_series,
        spy_equity,
        total_trading_costs,
        turnover_notional,
        STARTING_CAPITAL
    )

    return {
        "equity_series":
        equity_series,

        "metrics":
        metrics,

        "rebalance_count":
        rebalance_count
    }


def build_scaled_equal_weight_control(
    control_equity,
    spy_equity,
    invested_weight,
    label
):
    if (
        control_equity is None
        or
        control_equity.empty
        or
        spy_equity is None
        or
        spy_equity.empty
    ):
        return {
            "label":
            label,

            "invested_weight":
            invested_weight,

            "cash_weight":
            round(
                1
                -
                invested_weight,
                4
            ),

            "performance":
            {}
        }

    invested_weight = min(
        1.0,
        max(
            0.0,
            safe_float(
                invested_weight,
                0.0
            )
        )
    )

    control_returns = (
        control_equity
        .pct_change()
        .fillna(
            0.0
        )
    )

    scaled_returns = (
        control_returns
        *
        invested_weight
    )

    scaled_equity = (
        (
            1
            +
            scaled_returns
        )
        .cumprod()
        *
        STARTING_CAPITAL
    )

    metrics = calculate_equity_metrics(
        scaled_equity,
        spy_equity.reindex(
            scaled_equity.index
        ),
        0.0,
        0.0,
        STARTING_CAPITAL
    )

    return {
        "label":
        label,

        "invested_weight":
        round(
            invested_weight,
            4
        ),

        "cash_weight":
        round(
            1
            -
            invested_weight,
            4
        ),

        "performance":
        metrics,

        "cost_model_note":
        (
            "Scaled from the already net-of-friction equal-weight control "
            "return stream; displayed trading-cost field is zero because no "
            "second cost layer is applied."
        )
    }


def find_drawdown_matched_weight(
    control_equity,
    spy_equity,
    target_max_drawdown_pct
):
    """
    Find the constant equal-weight exposure whose max drawdown is as close as
    possible to AURORA's max drawdown. Cash is assumed to have zero return.

    The underlying control equity is already net of its modeled trading
    friction, so the scaled return stream inherits that friction effect.
    """

    target = safe_float(
        target_max_drawdown_pct,
        0
    )

    if (
        control_equity is None
        or
        control_equity.empty
        or
        target <= 0
    ):
        return 0.0

    low = 0.0
    high = 1.0

    best_weight = 0.0
    best_distance = float(
        "inf"
    )

    for _ in range(
        32
    ):
        mid = (
            low
            +
            high
        ) / 2

        candidate = (
            build_scaled_equal_weight_control(
                control_equity,
                spy_equity,
                mid,
                "Drawdown-Matched Equal Weight / Cash"
            )
        )

        max_dd = safe_float(
            (
                candidate.get(
                    "performance",
                    {}
                )
                or
                {}
            ).get(
                "max_drawdown_pct"
            ),
            0
        )

        distance = abs(
            max_dd
            -
            target
        )

        if distance < best_distance:
            best_distance = distance
            best_weight = mid

        if max_dd > target:
            high = mid
        else:
            low = mid

    return min(
        1.0,
        max(
            0.0,
            best_weight
        )
    )



def build_rolling_oos_exposure_attribution(
    strategy_equity,
    control_equity,
    spy_equity
):
    """
    V8.4.4 rolling out-of-sample exposure attribution.

    At each monthly decision point:
    - estimate AURORA/control risk using only the prior 126 sessions;
    - freeze the resulting control/cash weight for the next 21 sessions;
    - never use future returns to set the exposure for that test block.

    Two controls are produced:
    1) trailing-volatility-matched equal weight / cash;
    2) trailing-drawdown-calibrated equal weight / cash.

    Cash return is 0%. The source equal-weight return stream is already
    net of its modeled trading friction. No second friction layer is added
    when exposure changes, which is favorable to the control benchmark.
    """

    if (
        strategy_equity is None
        or strategy_equity.empty
        or control_equity is None
        or control_equity.empty
        or spy_equity is None
        or spy_equity.empty
    ):
        return {
            "version": "V8.4.4",
            "status": "INSUFFICIENT_DATA",
            "verdict": "UNDETERMINED",
            "calibration_gate": "RESEARCH_ONLY",
            "live_execution_authorized": False
        }

    aligned = pd.concat(
        [
            strategy_equity.rename("aurora"),
            control_equity.rename("equal_weight")
        ],
        axis=1,
        join="inner"
    ).dropna()

    returns_frame = (
        aligned
        .pct_change()
        .replace(
            [np.inf, -np.inf],
            np.nan
        )
        .dropna()
    )

    minimum_required = (
        ROLLING_OOS_LOOKBACK_SESSIONS
        +
        ROLLING_OOS_REBALANCE_SESSIONS
    )

    if len(returns_frame) < minimum_required:
        return {
            "version": "V8.4.4",
            "status": "INSUFFICIENT_DATA",
            "verdict": "UNDETERMINED",
            "available_return_sessions": len(returns_frame),
            "minimum_required_sessions": minimum_required,
            "calibration_gate": "RESEARCH_ONLY",
            "live_execution_authorized": False
        }

    def max_drawdown_from_returns(return_series):
        if return_series is None or return_series.empty:
            return 0.0

        compounded = (
            (
                1.0
                +
                return_series
            )
            .cumprod()
            .to_numpy(
                dtype=float
            )
        )

        equity_values = np.concatenate(
            (
                np.array(
                    [1.0],
                    dtype=float
                ),
                compounded
            )
        )

        running_max = np.maximum.accumulate(
            equity_values
        )

        drawdown = (
            equity_values
            /
            running_max
            -
            1.0
        )

        return abs(
            safe_float(
                np.min(
                    drawdown
                ),
                0.0
            )
        ) * 100

    def trailing_drawdown_matched_weight(
        control_returns,
        target_drawdown_pct
    ):
        target = max(
            0.0,
            safe_float(
                target_drawdown_pct,
                0.0
            )
        )

        if (
            control_returns is None
            or control_returns.empty
            or target <= 0
        ):
            return 0.0

        low = 0.0
        high = 1.0
        best_weight = 0.0
        best_distance = float("inf")

        for _ in range(32):
            mid = (low + high) / 2

            candidate_drawdown = (
                max_drawdown_from_returns(
                    control_returns
                    *
                    mid
                )
            )

            distance = abs(
                candidate_drawdown
                -
                target
            )

            if distance < best_distance:
                best_distance = distance
                best_weight = mid

            if candidate_drawdown > target:
                high = mid
            else:
                low = mid

        return min(
            1.0,
            max(
                0.0,
                best_weight
            )
        )

    strategy_oos_parts = []
    control_oos_parts = []
    vol_matched_parts = []
    dd_matched_parts = []
    exposure_history = []

    for start in range(
        ROLLING_OOS_LOOKBACK_SESSIONS,
        len(returns_frame),
        ROLLING_OOS_REBALANCE_SESSIONS
    ):
        train = returns_frame.iloc[
            start
            -
            ROLLING_OOS_LOOKBACK_SESSIONS:
            start
        ]

        test = returns_frame.iloc[
            start:
            start
            +
            ROLLING_OOS_REBALANCE_SESSIONS
        ]

        if train.empty or test.empty:
            continue

        strategy_std = safe_float(
            train["aurora"].std(),
            0.0
        )

        control_std = safe_float(
            train["equal_weight"].std(),
            0.0
        )

        volatility_weight = (
            min(
                1.0,
                max(
                    0.0,
                    strategy_std
                    /
                    control_std
                )
            )
            if control_std > 0
            else 0.0
        )

        target_training_drawdown = (
            max_drawdown_from_returns(
                train["aurora"]
            )
        )

        drawdown_weight = (
            trailing_drawdown_matched_weight(
                train["equal_weight"],
                target_training_drawdown
            )
        )

        strategy_oos_parts.append(
            test["aurora"]
        )

        control_oos_parts.append(
            test["equal_weight"]
        )

        vol_matched_parts.append(
            test["equal_weight"]
            *
            volatility_weight
        )

        dd_matched_parts.append(
            test["equal_weight"]
            *
            drawdown_weight
        )

        exposure_history.append({
            "decision_date":
            str(
                train.index[-1].date()
            ),

            "test_start_date":
            str(
                test.index[0].date()
            ),

            "test_end_date":
            str(
                test.index[-1].date()
            ),

            "test_sessions":
            len(test),

            "trailing_sessions":
            len(train),

            "trailing_aurora_volatility_pct":
            round(
                strategy_std
                *
                math.sqrt(252)
                *
                100,
                2
            ),

            "trailing_equal_weight_volatility_pct":
            round(
                control_std
                *
                math.sqrt(252)
                *
                100,
                2
            ),

            "volatility_matched_invested_weight":
            round(
                volatility_weight,
                4
            ),

            "volatility_matched_cash_weight":
            round(
                1.0
                -
                volatility_weight,
                4
            ),

            "trailing_aurora_max_drawdown_pct":
            round(
                target_training_drawdown,
                2
            ),

            "drawdown_calibrated_invested_weight":
            round(
                drawdown_weight,
                4
            ),

            "drawdown_calibrated_cash_weight":
            round(
                1.0
                -
                drawdown_weight,
                4
            )
        })

    if not strategy_oos_parts:
        return {
            "version": "V8.4.4",
            "status": "INSUFFICIENT_DATA",
            "verdict": "UNDETERMINED",
            "calibration_gate": "RESEARCH_ONLY",
            "live_execution_authorized": False
        }

    strategy_oos_returns = pd.concat(
        strategy_oos_parts
    ).sort_index()

    control_oos_returns = pd.concat(
        control_oos_parts
    ).sort_index()

    vol_matched_returns = pd.concat(
        vol_matched_parts
    ).sort_index()

    dd_matched_returns = pd.concat(
        dd_matched_parts
    ).sort_index()

    common_index = (
        strategy_oos_returns.index
        .intersection(control_oos_returns.index)
        .intersection(vol_matched_returns.index)
        .intersection(dd_matched_returns.index)
    )

    strategy_oos_returns = (
        strategy_oos_returns
        .reindex(common_index)
        .dropna()
    )

    control_oos_returns = (
        control_oos_returns
        .reindex(strategy_oos_returns.index)
        .dropna()
    )

    vol_matched_returns = (
        vol_matched_returns
        .reindex(strategy_oos_returns.index)
        .dropna()
    )

    dd_matched_returns = (
        dd_matched_returns
        .reindex(strategy_oos_returns.index)
        .dropna()
    )

    common_index = (
        strategy_oos_returns.index
        .intersection(control_oos_returns.index)
        .intersection(vol_matched_returns.index)
        .intersection(dd_matched_returns.index)
    )

    if len(common_index) < 2:
        return {
            "version": "V8.4.4",
            "status": "INSUFFICIENT_DATA",
            "verdict": "UNDETERMINED",
            "calibration_gate": "RESEARCH_ONLY",
            "live_execution_authorized": False
        }

    strategy_oos_returns = strategy_oos_returns.reindex(
        common_index
    )

    control_oos_returns = control_oos_returns.reindex(
        common_index
    )

    vol_matched_returns = vol_matched_returns.reindex(
        common_index
    )

    dd_matched_returns = dd_matched_returns.reindex(
        common_index
    )

    first_oos_date = common_index[0]

    first_position = aligned.index.get_indexer(
        [first_oos_date]
    )[0]

    if first_position <= 0:
        return {
            "version": "V8.4.4",
            "status": "INSUFFICIENT_DATA",
            "verdict": "UNDETERMINED",
            "calibration_gate": "RESEARCH_ONLY",
            "live_execution_authorized": False
        }

    base_date = aligned.index[
        first_position
        -
        1
    ]

    def equity_from_returns(return_series):
        compounded = (
            (
                1.0
                +
                return_series
            )
            .cumprod()
            *
            STARTING_CAPITAL
        )

        base = pd.Series(
            [STARTING_CAPITAL],
            index=pd.DatetimeIndex(
                [base_date]
            ),
            dtype=float
        )

        return pd.concat(
            [
                base,
                compounded
            ]
        ).sort_index()

    strategy_oos_equity = equity_from_returns(
        strategy_oos_returns
    )

    control_oos_equity = equity_from_returns(
        control_oos_returns
    )

    vol_matched_equity = equity_from_returns(
        vol_matched_returns
    )

    dd_matched_equity = equity_from_returns(
        dd_matched_returns
    )

    strategy_metrics = calculate_equity_metrics(
        strategy_oos_equity,
        spy_equity,
        0.0,
        0.0,
        STARTING_CAPITAL
    )

    control_metrics = calculate_equity_metrics(
        control_oos_equity,
        spy_equity,
        0.0,
        0.0,
        STARTING_CAPITAL
    )

    vol_metrics = calculate_equity_metrics(
        vol_matched_equity,
        spy_equity,
        0.0,
        0.0,
        STARTING_CAPITAL
    )

    dd_metrics = calculate_equity_metrics(
        dd_matched_equity,
        spy_equity,
        0.0,
        0.0,
        STARTING_CAPITAL
    )

    vol_cagr_advantage = round(
        safe_float(
            strategy_metrics.get("cagr_pct"),
            0.0
        )
        -
        safe_float(
            vol_metrics.get("cagr_pct"),
            0.0
        ),
        2
    )

    vol_sharpe_advantage = round(
        safe_float(
            strategy_metrics.get("sharpe_ratio"),
            0.0
        )
        -
        safe_float(
            vol_metrics.get("sharpe_ratio"),
            0.0
        ),
        3
    )

    vol_drawdown_advantage = round(
        safe_float(
            vol_metrics.get("max_drawdown_pct"),
            0.0
        )
        -
        safe_float(
            strategy_metrics.get("max_drawdown_pct"),
            0.0
        ),
        2
    )

    dd_cagr_advantage = round(
        safe_float(
            strategy_metrics.get("cagr_pct"),
            0.0
        )
        -
        safe_float(
            dd_metrics.get("cagr_pct"),
            0.0
        ),
        2
    )

    dd_sharpe_advantage = round(
        safe_float(
            strategy_metrics.get("sharpe_ratio"),
            0.0
        )
        -
        safe_float(
            dd_metrics.get("sharpe_ratio"),
            0.0
        ),
        3
    )

    dd_drawdown_advantage = round(
        safe_float(
            dd_metrics.get("max_drawdown_pct"),
            0.0
        )
        -
        safe_float(
            strategy_metrics.get("max_drawdown_pct"),
            0.0
        ),
        2
    )

    if (
        vol_cagr_advantage > 0
        and vol_sharpe_advantage > 0
        and (
            vol_drawdown_advantage >= 0
            or dd_cagr_advantage > 0
        )
    ):
        verdict = "OOS_RISK_ADJUSTED_SUPPORTIVE"
    elif (
        vol_drawdown_advantage > 0
        and vol_cagr_advantage <= 0
    ):
        verdict = "OOS_DRAWDOWN_ONLY_NO_RETURN_ALPHA"
    elif (
        vol_cagr_advantage <= 0
        and vol_sharpe_advantage <= 0
        and vol_drawdown_advantage <= 0
    ):
        verdict = "OOS_NOT_VALIDATED"
    else:
        verdict = "OOS_MIXED_EVIDENCE"

    vol_weights = [
        safe_float(
            item.get(
                "volatility_matched_invested_weight"
            ),
            0.0
        )
        for item in exposure_history
    ]

    dd_weights = [
        safe_float(
            item.get(
                "drawdown_calibrated_invested_weight"
            ),
            0.0
        )
        for item in exposure_history
    ]

    evidence_strength = (
        "MODERATE"
        if len(common_index) >= 504
        else
        "LIMITED"
        if len(common_index) >= 252
        else
        "LOW"
    )

    return {
        "version":
        "V8.4.4",

        "status":
        "COMPLETE",

        "verdict":
        verdict,

        "calibration_gate":
        "RESEARCH_ONLY",

        "live_execution_authorized":
        False,

        "evidence_strength":
        evidence_strength,

        "maximum_evidence_grade":
        "MODERATE_DUE_TO_CURRENT_HOLDINGS_SURVIVORSHIP_BIAS",

        "first_scored_date":
        str(
            first_oos_date.date()
        ),

        "last_scored_date":
        str(
            common_index[-1].date()
        ),

        "oos_sessions":
        len(common_index),

        "lookback_sessions":
        ROLLING_OOS_LOOKBACK_SESSIONS,

        "rebalance_sessions":
        ROLLING_OOS_REBALANCE_SESSIONS,

        "performance": {
            "aurora_oos":
            strategy_metrics,

            "equal_weight_100pct_oos":
            control_metrics,

            "rolling_volatility_matched_equal_weight":
            vol_metrics,

            "rolling_trailing_drawdown_matched_equal_weight":
            dd_metrics
        },

        "comparison": {
            "vol_matched_cagr_advantage_pct":
            vol_cagr_advantage,

            "vol_matched_sharpe_advantage":
            vol_sharpe_advantage,

            "vol_matched_drawdown_advantage_pct":
            vol_drawdown_advantage,

            "drawdown_matched_cagr_advantage_pct":
            dd_cagr_advantage,

            "drawdown_matched_sharpe_advantage":
            dd_sharpe_advantage,

            "drawdown_matched_drawdown_advantage_pct":
            dd_drawdown_advantage
        },

        "exposure_summary": {
            "volatility_matched_average_invested_weight":
            round(
                sum(vol_weights)
                /
                len(vol_weights),
                4
            )
            if vol_weights
            else None,

            "volatility_matched_min_invested_weight":
            round(
                min(vol_weights),
                4
            )
            if vol_weights
            else None,

            "volatility_matched_max_invested_weight":
            round(
                max(vol_weights),
                4
            )
            if vol_weights
            else None,

            "drawdown_calibrated_average_invested_weight":
            round(
                sum(dd_weights)
                /
                len(dd_weights),
                4
            )
            if dd_weights
            else None,

            "drawdown_calibrated_min_invested_weight":
            round(
                min(dd_weights),
                4
            )
            if dd_weights
            else None,

            "drawdown_calibrated_max_invested_weight":
            round(
                max(dd_weights),
                4
            )
            if dd_weights
            else None
        },

        "exposure_history":
        exposure_history,

        "methodology_note":
        (
            "Every exposure decision is estimated only from the prior 126 "
            "sessions and frozen for the next 21 sessions. No future return "
            "is used to set that block's benchmark exposure."
        ),

        "cost_model_note":
        (
            "AURORA and the 100% equal-weight source return streams already "
            "contain their modeled trading friction. Rolling control returns "
            "are scaled from that net control stream, but no additional cost "
            "is charged for monthly cash/exposure changes. This is favorable "
            "to the benchmark and therefore conservative for AURORA."
        ),

        "scope_note":
        (
            "This is out-of-sample exposure attribution for the reconstructable "
            "price/risk overlay on the current holdings universe. It does not "
            "remove survivorship/selection bias and is not statistical proof "
            "of full-system alpha."
        )
    }



def enrich_folds_with_control(
    folds,
    control_equity
):
    if (
        not folds
        or
        control_equity is None
        or
        control_equity.empty
    ):
        return folds

    enriched = []

    for fold in folds:
        try:
            start_date = pd.Timestamp(
                fold.get(
                    "start_date"
                )
            )

            end_date = pd.Timestamp(
                fold.get(
                    "end_date"
                )
            )

            control_slice = control_equity.loc[
                start_date:
                end_date
            ].dropna()

            control_return = None

            if len(
                control_slice
            ) >= 2:
                control_return = (
                    safe_float(
                        control_slice.iloc[-1]
                    )
                    /
                    safe_float(
                        control_slice.iloc[0]
                    )
                    -
                    1
                ) * 100

            strategy_return = safe_float(
                fold.get(
                    "strategy_return_pct"
                ),
                0
            )

            enriched.append({
                **fold,

                "equal_weight_control_return_pct":
                (
                    round(
                        control_return,
                        2
                    )
                    if control_return is not None
                    else None
                ),

                "overlay_excess_vs_control_pct":
                (
                    round(
                        strategy_return
                        -
                        control_return,
                        2
                    )
                    if control_return is not None
                    else None
                )
            })

        except Exception:
            enriched.append(
                fold
            )

    return enriched


def classify_validation_verdict(
    overlay_alpha,
    signal_validation
):
    cagr_alpha = safe_float(
        overlay_alpha.get(
            "cagr_alpha_pct"
        ),
        0
    )

    drawdown_improvement = safe_float(
        overlay_alpha.get(
            "max_drawdown_improvement_pct"
        ),
        0
    )

    sharpe_improvement = safe_float(
        overlay_alpha.get(
            "sharpe_improvement"
        ),
        0
    )

    hit_rate = safe_float(
        signal_validation.get(
            "hit_rate_pct"
        ),
        0
    )

    if (
        cagr_alpha >= 2
        and
        sharpe_improvement > 0
        and
        hit_rate >= 52
    ):
        return {
            "status":
            "PROMISING",

            "message":
            (
                "Strategic overlay adds return and risk-adjusted value versus "
                "the same-universe equal-weight control."
            )
        }

    if (
        cagr_alpha < -5
        and
        drawdown_improvement > 5
    ):
        return {
            "status":
            "RISK_REDUCTION_RETURN_SACRIFICE",

            "message":
            (
                "Strategic overlay materially reduces drawdown but sacrifices "
                "too much return versus the same-universe control. Thresholds "
                "should be recalibrated before relying on the overlay."
            )
        }

    if (
        cagr_alpha < 0
        and
        sharpe_improvement <= 0
    ):
        return {
            "status":
            "NOT_VALIDATED",

            "message":
            (
                "Strategic overlay does not add return or risk-adjusted value "
                "versus the same-universe control."
            )
        }

    return {
        "status":
        "INCONCLUSIVE",

        "message":
        (
            "Evidence is mixed. More out-of-sample history or policy "
            "calibration is required."
        )
    }


def serialize_equity_sample(
    equity_series,
    spy_equity
):
    if (
        equity_series is None
        or
        equity_series.empty
    ):
        return []

    sample_every = max(
        1,
        len(
            equity_series
        )
        //
        120
    )

    rows = []

    for index in range(
        0,
        len(
            equity_series
        ),
        sample_every
    ):
        date_value = equity_series.index[
            index
        ]

        rows.append({
            "date":
            str(
                date_value.date()
            ),

            "strategy_value":
            round(
                safe_float(
                    equity_series.iloc[
                        index
                    ]
                ),
                2
            ),

            "spy_value":
            round(
                safe_float(
                    spy_equity.reindex(
                        equity_series.index
                    ).iloc[
                        index
                    ]
                ),
                2
            )
        })

    last_date = equity_series.index[
        -1
    ]

    if (
        not rows
        or
        rows[-1].get(
            "date"
        )
        !=
        str(
            last_date.date()
        )
    ):
        rows.append({
            "date":
            str(
                last_date.date()
            ),

            "strategy_value":
            round(
                safe_float(
                    equity_series.iloc[
                        -1
                    ]
                ),
                2
            ),

            "spy_value":
            round(
                safe_float(
                    spy_equity.reindex(
                        equity_series.index
                    ).iloc[
                        -1
                    ]
                ),
                2
            )
        })

    return rows


def run_walk_forward_backtest(
    portfolio_rows,
    force=False
):
    tickers = [
        str(
            row.get(
                "ticker",
                ""
            )
        ).strip().upper()
        for row in portfolio_rows
        if str(
            row.get(
                "ticker",
                ""
            )
        ).strip()
    ]

    tickers = list(
        dict.fromkeys(
            tickers
        )
    )

    all_tickers = tickers + [
        "SPY"
    ]

    close_frame = (
        download_close_history(
            all_tickers
        )
    )

    if (
        close_frame.empty
        or
        "SPY"
        not in close_frame.columns
    ):
        result = {
            "engine":
            ENGINE_VERSION,

            "backtest_signature":
            BACKTEST_SIGNATURE,

            "status":
            "NO_DATA",

            "generated":
            datetime.now(
                timezone.utc
            ).isoformat(),

            "note":
            "Historical daily data unavailable."
        }

        save_result(
            result
        )

        return result

    market_date = str(
        close_frame[
            "SPY"
        ].dropna().index[-1].date()
    )

    signature = portfolio_signature(
        tickers
    )

    if not force:
        cached = load_cached_result(
            signature,
            market_date
        )

        if cached is not None:
            return cached

    start_date = find_start_date(
        close_frame,
        tickers
    )

    if start_date is None:
        result = {
            "engine":
            ENGINE_VERSION,

            "backtest_signature":
            BACKTEST_SIGNATURE,

            "portfolio_signature":
            signature,

            "market_date":
            market_date,

            "status":
            "INSUFFICIENT_HISTORY",

            "generated":
            datetime.now(
                timezone.utc
            ).isoformat()
        }

        save_result(
            result
        )

        return result

    simulation = simulate_strategy(
        close_frame,
        tickers,
        start_date
    )

    control_simulation = (
        simulate_equal_weight_control(
            close_frame,
            tickers,
            start_date
        )
    )

    if simulation is None:
        result = {
            "engine":
            ENGINE_VERSION,

            "backtest_signature":
            BACKTEST_SIGNATURE,

            "portfolio_signature":
            signature,

            "market_date":
            market_date,

            "status":
            "INSUFFICIENT_TEST_WINDOW",

            "generated":
            datetime.now(
                timezone.utc
            ).isoformat()
        }

        save_result(
            result
        )

        return result

    coverage = {}

    for ticker in tickers:
        if ticker not in close_frame.columns:
            coverage[
                ticker
            ] = {
                "available":
                False,

                "observations":
                0,

                "first_date":
                None,

                "last_date":
                None
            }

            continue

        series = close_frame[
            ticker
        ].dropna()

        coverage[
            ticker
        ] = {
            "available":
            not series.empty,

            "observations":
            len(
                series
            ),

            "first_date":
            (
                str(
                    series.index[0].date()
                )
                if not series.empty
                else None
            ),

            "last_date":
            (
                str(
                    series.index[-1].date()
                )
                if not series.empty
                else None
            )
        }

    equity_sample = serialize_equity_sample(
        simulation.get(
            "equity_series"
        ),
        simulation.get(
            "spy_equity"
        )
    )

    strategy_metrics = (
        simulation.get(
            "metrics",
            {}
        )
        or
        {}
    )

    control_metrics = (
        (
            control_simulation
            or
            {}
        ).get(
            "metrics",
            {}
        )
        or
        {}
    )

    control_equity = (
        (
            control_simulation
            or
            {}
        ).get(
            "equity_series"
        )
    )

    spy_equity = simulation.get(
        "spy_equity"
    )

    strategy_vol = safe_float(
        strategy_metrics.get(
            "annualized_volatility_pct"
        ),
        0
    )

    control_vol = safe_float(
        control_metrics.get(
            "annualized_volatility_pct"
        ),
        0
    )

    volatility_matched_weight = (
        min(
            1.0,
            max(
                0.0,
                strategy_vol
                /
                control_vol
            )
        )
        if control_vol
        >
        0
        else
        0.65
    )

    drawdown_matched_weight = (
        find_drawdown_matched_weight(
            control_equity,
            spy_equity,
            strategy_metrics.get(
                "max_drawdown_pct"
            )
        )
    )

    risk_scaled_controls = {
        "equal_weight_75_25":
        build_scaled_equal_weight_control(
            control_equity,
            spy_equity,
            0.75,
            "75% Equal Weight / 25% Cash"
        ),

        "equal_weight_65_35":
        build_scaled_equal_weight_control(
            control_equity,
            spy_equity,
            0.65,
            "65% Equal Weight / 35% Cash"
        ),

        "volatility_matched_equal_weight":
        build_scaled_equal_weight_control(
            control_equity,
            spy_equity,
            volatility_matched_weight,
            "Volatility-Matched Equal Weight / Cash"
        ),

        "drawdown_matched_equal_weight":
        build_scaled_equal_weight_control(
            control_equity,
            spy_equity,
            drawdown_matched_weight,
            "Drawdown-Matched Equal Weight / Cash"
        )
    }

    strategy_cagr = safe_float(
        strategy_metrics.get(
            "cagr_pct"
        ),
        0
    )

    control_cagr = safe_float(
        control_metrics.get(
            "cagr_pct"
        ),
        0
    )

    strategy_total_return = safe_float(
        strategy_metrics.get(
            "total_return_pct"
        ),
        0
    )

    control_total_return = safe_float(
        control_metrics.get(
            "total_return_pct"
        ),
        0
    )

    overlay_alpha_vs_control = {
        "cagr_alpha_pct":
        round(
            strategy_cagr
            -
            control_cagr,
            2
        ),

        "total_return_difference_pct":
        round(
            strategy_total_return
            -
            control_total_return,
            2
        ),

        "max_drawdown_improvement_pct":
        round(
            safe_float(
                control_metrics.get(
                    "max_drawdown_pct"
                ),
                0
            )
            -
            safe_float(
                strategy_metrics.get(
                    "max_drawdown_pct"
                ),
                0
            ),
            2
        ),

        "sharpe_improvement":
        round(
            safe_float(
                strategy_metrics.get(
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
        )
    }

    signal_validation = (
        simulation.get(
            "signal_validation",
            {}
        )
        or
        {}
    )

    validation_verdict = (
        classify_validation_verdict(
            overlay_alpha_vs_control,
            signal_validation
        )
    )

    walk_forward_folds = (
        enrich_folds_with_control(
            simulation.get(
                "walk_forward_folds",
                []
            ),
            (
                (
                    control_simulation
                    or
                    {}
                ).get(
                    "equity_series"
                )
            )
        )
    )

    risk_scaled_comparison = {}

    for key, item in (
        risk_scaled_controls.items()
    ):
        metrics = (
            item.get(
                "performance",
                {}
            )
            or
            {}
        )

        risk_scaled_comparison[
            key
        ] = {
            **item,

            "aurora_cagr_advantage_pct":
            round(
                safe_float(
                    strategy_metrics.get(
                        "cagr_pct"
                    ),
                    0
                )
                -
                safe_float(
                    metrics.get(
                        "cagr_pct"
                    ),
                    0
                ),
                2
            ),

            "aurora_sharpe_advantage":
            round(
                safe_float(
                    strategy_metrics.get(
                        "sharpe_ratio"
                    ),
                    0
                )
                -
                safe_float(
                    metrics.get(
                        "sharpe_ratio"
                    ),
                    0
                ),
                3
            ),

            "aurora_drawdown_advantage_pct":
            round(
                safe_float(
                    metrics.get(
                        "max_drawdown_pct"
                    ),
                    0
                )
                -
                safe_float(
                    strategy_metrics.get(
                        "max_drawdown_pct"
                    ),
                    0
                ),
                2
            )
        }

    rolling_oos_attribution = (
        build_rolling_oos_exposure_attribution(
            simulation.get(
                "equity_series"
            ),
            control_equity,
            spy_equity
        )
    )

    # V8.4.3: descriptive exposure attribution (not causal proof).
    # Risk matching is fitted on the entire evaluation sample, so these
    # figures are in-sample diagnostics and never authorize live trading.
    vol_control = risk_scaled_comparison.get(
        "volatility_matched_equal_weight", {}
    )
    dd_control = risk_scaled_comparison.get(
        "drawdown_matched_equal_weight", {}
    )
    vol_perf = vol_control.get("performance", {}) or {}
    dd_perf = dd_control.get("performance", {}) or {}

    required = (
        "cagr_pct", "sharpe_ratio", "max_drawdown_pct",
        "annualized_volatility_pct"
    )
    valid = all(
        isinstance(block.get(field), (int, float))
        and math.isfinite(float(block[field]))
        for block in (strategy_metrics, control_metrics, vol_perf, dd_perf)
        for field in required
    )
    if valid:
        vol_cagr_delta = round(
            strategy_metrics["cagr_pct"] - vol_perf["cagr_pct"], 2
        )
        vol_sharpe_delta = round(
            strategy_metrics["sharpe_ratio"] - vol_perf["sharpe_ratio"], 3
        )
        vol_dd_advantage = round(
            vol_perf["max_drawdown_pct"] -
            strategy_metrics["max_drawdown_pct"], 2
        )
        dd_cagr_advantage = round(
            strategy_metrics["cagr_pct"] - dd_perf["cagr_pct"], 2
        )
        raw_dd_reduction = (
            control_metrics["max_drawdown_pct"] -
            strategy_metrics["max_drawdown_pct"]
        )
        exposure_dd_reduction = (
            control_metrics["max_drawdown_pct"] -
            vol_perf["max_drawdown_pct"]
        )
        cash_explained_share = (
            round(exposure_dd_reduction / raw_dd_reduction * 100, 2)
            if raw_dd_reduction > 0 else None
        )
        if vol_cagr_delta > 0 and vol_sharpe_delta > 0:
            verdict = "RISK_ADJUSTED_OUTPERFORMANCE_CANDIDATE"
        elif vol_dd_advantage > 0 and dd_cagr_advantage > 0:
            verdict = "DRAWDOWN_PATH_ADVANTAGE_NO_VOL_ALPHA"
        elif vol_dd_advantage > 0:
            verdict = "DRAWDOWN_ADVANTAGE_WITH_RETURN_TRADEOFF"
        else:
            verdict = "EXPOSURE_DOMINATED_NO_PROVEN_ALPHA"

        exposure_attribution = {
            "version": "V8.4.3",
            "status": "COMPLETE",
            "verdict": verdict,
            "vol_matched_cagr_advantage_pct": vol_cagr_delta,
            "vol_matched_sharpe_advantage": vol_sharpe_delta,
            "vol_matched_drawdown_advantage_pct": vol_dd_advantage,
            "dd_matched_cagr_advantage_pct": dd_cagr_advantage,
            "drawdown_reduction_from_full_ew_pct_points":
                round(raw_dd_reduction, 2),
            "drawdown_reduction_by_vol_scaled_control_pct_points":
                round(exposure_dd_reduction, 2),
            "exposure_proxy_share_of_drawdown_reduction_pct":
                cash_explained_share,
            "exposure_proxy_note":
                "Descriptive proxy only; drawdown is nonlinear and this "
                "ratio is not a causal decomposition.",
            "calibration_gate": "RESEARCH_ONLY",
            "live_execution_authorized": False,
            "methodology_note":
                "Full-sample volatility/drawdown-matched cash allocations "
                "use contemporaneous strategy risk. They are hindsight-fit "
                "diagnostics, not independent out-of-sample benchmarks."
        }
    else:
        exposure_attribution = {
            "version": "V8.4.3",
            "status": "INSUFFICIENT_DATA",
            "verdict": "UNDETERMINED",
            "calibration_gate": "RESEARCH_ONLY",
            "live_execution_authorized": False
        }

    result = {
        "engine":
        ENGINE_VERSION,

        "backtest_signature":
        BACKTEST_SIGNATURE,

        "portfolio_signature":
        signature,

        "cache_status":
        "FRESH",

        "status":
        "COMPLETE",

        "generated":
        datetime.now(
            timezone.utc
        ).isoformat(),

        "market_date":
        market_date,

        "validation_scope":
        "CURRENT_PORTFOLIO_STRATEGIC_PRICE_RISK_LAYER",

        "start_date":
        str(
            start_date.date()
        ),

        "end_date":
        market_date,

        "starting_capital":
        STARTING_CAPITAL,

        "portfolio_tickers":
        tickers,

        "methodology": {
            "signal_data":
            "Daily adjusted close only",

            "feature_horizons":
            "3M / 6M / 12M + SMA50/100/200 + SPY relative strength",

            "decision_timing":
            (
                "Features use data through prior session; "
                "weights execute next session close."
            ),

            "rebalance_frequency_sessions":
            REBALANCE_EVERY_SESSIONS,

            "walk_forward_fold_sessions":
            WALK_FORWARD_FOLD_SESSIONS,

            "rolling_oos_exposure_lookback_sessions":
            ROLLING_OOS_LOOKBACK_SESSIONS,

            "rolling_oos_exposure_rebalance_sessions":
            ROLLING_OOS_REBALANCE_SESSIONS,

            "minimum_warmup_sessions":
            MIN_WARMUP_SESSIONS,

            "minimum_eligible_ratio":
            MIN_ELIGIBLE_RATIO,

            "commission_bps":
            COMMISSION_BPS,

            "slippage_bps":
            SLIPPAGE_BPS,

            "total_friction_bps":
            TOTAL_TRADING_FRICTION_BPS,

            "cash_allowed":
            True,

            "weighting":
            (
                "Equal base weight across eligible current portfolio names, "
                "then strategic exposure multipliers HOLD=1.0, WATCH=0.75, "
                "REDUCE=0.50, EXIT=0.0."
            )
        },

        "performance":
        strategy_metrics,

        "equal_weight_control": {
            "description":
            (
                "Same current portfolio names, same historical eligibility, "
                "same weekly rebalance timing and same trading friction, "
                "but without the strategic de-risking overlay."
            ),

            "performance":
            control_metrics,

            "rebalance_count":
            (
                control_simulation
                or
                {}
            ).get(
                "rebalance_count",
                0
            )
        },

        "risk_scaled_equal_weight_controls":
        risk_scaled_comparison,

        "exposure_attribution_verdict":
        exposure_attribution,

        "rolling_oos_exposure_attribution":
        rolling_oos_attribution,

        "overlay_alpha_vs_equal_weight_control":
        overlay_alpha_vs_control,

        "validation_verdict":
        validation_verdict,

        "signal_validation":
        signal_validation,

        "walk_forward_folds":
        walk_forward_folds,

        "rebalance_count":
        simulation.get(
            "rebalance_count",
            0
        ),

        "signal_change_count":
        simulation.get(
            "signal_change_count",
            0
        ),

        "latest_replay_actions":
        simulation.get(
            "last_actions",
            {}
        ),

        "data_coverage":
        coverage,

        "equity_curve_sample":
        equity_sample,

        "limitations": [
            (
                "Historical news, catalyst and sector snapshots were not "
                "archived consistently and are intentionally excluded."
            ),
            (
                "The universe is today's portfolio, creating survivorship "
                "and selection bias. The equal-weight control uses the same "
                "biased universe so overlay-vs-control is more informative "
                "than strategy-vs-SPY for isolating the risk overlay."
            ),
            (
                "This validates the reconstructable strategic price/risk "
                "overlay, not the entire live AURORA decision stack."
            ),
            (
                "Taxes are excluded. Trading friction is modeled using the "
                "explicit commission and slippage assumptions above."
            ),
            (
                "No parameter optimization is performed inside the test "
                "window; sequential folds are fixed-rule out-of-sample replay."
            )
        ],

        "interpretation":
        (
            "Use this result as evidence about the V7.9 strategic price/risk "
            "layer. Do not use it as proof that the full AURORA system is "
            "profitable until point-in-time fundamental/news data and broker "
            "execution are also validated."
        )
    }

    save_result(
        result
    )

    return result
