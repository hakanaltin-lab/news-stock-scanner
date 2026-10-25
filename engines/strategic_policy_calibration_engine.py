"""
V8.1 AURORA Strategic Policy Calibration Lab

Purpose:
- Calibrate the V7.9 strategic de-risking policy without look-ahead
- Use a deliberately small, pre-declared policy family
- Select a policy using only prior training history
- Freeze that policy for the next out-of-sample fold
- Compare calibrated policy vs live V7.9 default and same-universe equal-weight control
- Recommend PROMOTE_CANDIDATE only when out-of-sample evidence is robust

Important:
- This lab does NOT automatically modify the live portfolio policy.
- No large parameter grid is searched.
- Current holdings still create survivorship / selection bias.
- Historical news/fundamental/event data are not reconstructed here.
- No broker orders are sent.
"""

from datetime import datetime, timezone
import hashlib
import json
import math
import os

import pandas as pd

from engines.walk_forward_backtest_engine import (
    STARTING_CAPITAL,
    TOTAL_TRADING_FRICTION_BPS,
    MIN_WARMUP_SESSIONS,
    WALK_FORWARD_FOLD_SESSIONS,
    calculate_equity_metrics,
    download_close_history,
    eligible_tickers_at_date,
    find_start_date,
    strategic_state_as_of,
    safe_float
)


ENGINE_VERSION = (
    "V8.1 Strategic Policy Calibration Lab"
)

CALIBRATION_SIGNATURE = "V8.1.1"

OUTPUT_FILE = "docs/strategic_policy_calibration.json"

TRAINING_SESSIONS_MIN = 252

OOS_FOLD_SESSIONS = WALK_FORWARD_FOLD_SESSIONS

REBALANCE_EVERY_SESSIONS = 5

MIN_DRAWDOWN_REDUCTION_RATIO = 0.15


POLICY_FAMILY = {
    "DEFAULT_V7_9": {
        "description":
        "Current live V7.9 strategic policy.",

        "exit_trend_max": 30,
        "exit_risk_max": 35,
        "exit_return_6m_max": -20,
        "exit_rs_6m_max": -15,

        "reduce_trend_max": 40,
        "reduce_return_6m_max": -8,
        "reduce_rs_6m_max": -8,

        "hold_trend_min": 65,
        "hold_risk_min": 45,
        "hold_return_6m_min": 0,
        "hold_rs_6m_min": 0,

        "hold_exposure": 1.00,
        "watch_exposure": 0.75,
        "reduce_exposure": 0.50,
        "exit_exposure": 0.00
    },

    "BALANCED_GENTLE": {
        "description":
        "Later exits and smaller de-risking steps.",

        "exit_trend_max": 25,
        "exit_risk_max": 30,
        "exit_return_6m_max": -25,
        "exit_rs_6m_max": -18,

        "reduce_trend_max": 35,
        "reduce_return_6m_max": -12,
        "reduce_rs_6m_max": -10,

        "hold_trend_min": 60,
        "hold_risk_min": 40,
        "hold_return_6m_min": 0,
        "hold_rs_6m_min": 0,

        "hold_exposure": 1.00,
        "watch_exposure": 0.90,
        "reduce_exposure": 0.65,
        "exit_exposure": 0.10
    },

    "RETURN_FRIENDLY": {
        "description":
        "Keeps more exposure during mixed trends while retaining hard risk exits.",

        "exit_trend_max": 20,
        "exit_risk_max": 25,
        "exit_return_6m_max": -30,
        "exit_rs_6m_max": -20,

        "reduce_trend_max": 30,
        "reduce_return_6m_max": -15,
        "reduce_rs_6m_max": -12,

        "hold_trend_min": 58,
        "hold_risk_min": 35,
        "hold_return_6m_min": 0,
        "hold_rs_6m_min": -2,

        "hold_exposure": 1.00,
        "watch_exposure": 0.95,
        "reduce_exposure": 0.75,
        "exit_exposure": 0.20
    },

    "MOMENTUM_FRIENDLY": {
        "description":
        "Avoids cutting positions unless long-horizon momentum is decisively broken.",

        "exit_trend_max": 20,
        "exit_risk_max": 22,
        "exit_return_6m_max": -25,
        "exit_rs_6m_max": -20,

        "reduce_trend_max": 30,
        "reduce_return_6m_max": -15,
        "reduce_rs_6m_max": -15,

        "hold_trend_min": 55,
        "hold_risk_min": 35,
        "hold_return_6m_min": -2,
        "hold_rs_6m_min": -3,

        "hold_exposure": 1.00,
        "watch_exposure": 0.97,
        "reduce_exposure": 0.80,
        "exit_exposure": 0.25
    },

    "RISK_AWARE_GENTLE": {
        "description":
        "Retains meaningful drawdown control but reduces the severity of partial exits.",

        "exit_trend_max": 25,
        "exit_risk_max": 28,
        "exit_return_6m_max": -25,
        "exit_rs_6m_max": -18,

        "reduce_trend_max": 35,
        "reduce_return_6m_max": -10,
        "reduce_rs_6m_max": -10,

        "hold_trend_min": 60,
        "hold_risk_min": 38,
        "hold_return_6m_min": 0,
        "hold_rs_6m_min": 0,

        "hold_exposure": 1.00,
        "watch_exposure": 0.88,
        "reduce_exposure": 0.70,
        "exit_exposure": 0.15
    }
}


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
                "calibration_signature"
            )
            !=
            CALIBRATION_SIGNATURE
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


def policy_action(
    state,
    policy
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
        trend_score
        <
        safe_float(
            policy.get(
                "exit_trend_max",
                30
            )
        )
        and
        above_sma200 is False
        and
        return_6m
        <=
        safe_float(
            policy.get(
                "exit_return_6m_max",
                -20
            )
        )
        and
        rs_6m
        <=
        safe_float(
            policy.get(
                "exit_rs_6m_max",
                -15
            )
        )
    )

    severe_risk_break = (
        risk_score
        <
        safe_float(
            policy.get(
                "exit_risk_max",
                35
            )
        )
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
        trend_score
        <
        safe_float(
            policy.get(
                "reduce_trend_max",
                40
            )
        )
        and
        above_sma200 is False
        and
        return_6m
        <
        safe_float(
            policy.get(
                "reduce_return_6m_max",
                -8
            )
        )
        and
        rs_6m
        <
        safe_float(
            policy.get(
                "reduce_rs_6m_max",
                -8
            )
        )
    ):
        return "REDUCE"

    if (
        trend_score
        >=
        safe_float(
            policy.get(
                "hold_trend_min",
                65
            )
        )
        and
        risk_score
        >=
        safe_float(
            policy.get(
                "hold_risk_min",
                45
            )
        )
        and
        above_sma200 is True
        and
        return_6m
        >
        safe_float(
            policy.get(
                "hold_return_6m_min",
                0
            )
        )
        and
        rs_6m
        >
        safe_float(
            policy.get(
                "hold_rs_6m_min",
                0
            )
        )
    ):
        return "HOLD"

    return "WATCH"


def policy_exposure(
    action,
    policy
):
    mapping = {
        "HOLD":
        safe_float(
            policy.get(
                "hold_exposure",
                1.0
            )
        ),

        "WATCH":
        safe_float(
            policy.get(
                "watch_exposure",
                0.75
            )
        ),

        "REDUCE":
        safe_float(
            policy.get(
                "reduce_exposure",
                0.50
            )
        ),

        "EXIT":
        safe_float(
            policy.get(
                "exit_exposure",
                0.0
            )
        )
    }

    return min(
        1.0,
        max(
            0.0,
            mapping.get(
                action,
                0.0
            )
        )
    )


def previous_trading_date(
    spy_dates,
    date_value
):
    eligible = [
        item
        for item in spy_dates
        if item < date_value
    ]

    if not eligible:
        return None

    return eligible[
        -1
    ]


def prices_as_of(
    close_frame,
    tickers,
    date_value
):
    prices = {}

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
                prices[
                    ticker
                ] = price

        except Exception:
            continue

    return prices


def build_policy_target_weights(
    decision_date,
    tickers,
    close_frame,
    policy
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

        action = policy_action(
            state,
            policy
        )

        exposure = policy_exposure(
            action,
            policy
        )

        states[
            ticker
        ] = {
            **state,

            "action":
            action,

            "exposure_multiplier":
            exposure
        }

        weights[
            ticker
        ] = (
            base_weight
            *
            exposure
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


def build_equal_weight_targets(
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
        return {}

    weight = (
        1.0
        /
        len(
            eligible
        )
    )

    return {
        ticker:
        weight
        for ticker in eligible
    }


def simulate_range(
    close_frame,
    tickers,
    start_date,
    end_date,
    policy=None,
    equal_weight=False
):
    spy = close_frame[
        "SPY"
    ].dropna()

    all_spy_dates = list(
        spy.index
    )

    trading_dates = [
        date_value
        for date_value in all_spy_dates
        if (
            date_value >= start_date
            and
            date_value <= end_date
        )
    ]

    if len(
        trading_dates
    ) < 20:
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

    action_changes = 0

    last_actions = {}

    for index, date_value in enumerate(
        trading_dates
    ):
        prices_today = prices_as_of(
            close_frame,
            tickers,
            date_value
        )

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

        if should_rebalance:
            decision_date = (
                previous_trading_date(
                    all_spy_dates,
                    date_value
                )
            )

            if decision_date is not None:
                if equal_weight:
                    target_weights = (
                        build_equal_weight_targets(
                            decision_date,
                            tickers,
                            close_frame
                        )
                    )

                    states = {}

                else:
                    (
                        target_weights,
                        states
                    ) = (
                        build_policy_target_weights(
                            decision_date,
                            tickers,
                            close_frame,
                            policy
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

                        if (
                            last_actions.get(
                                ticker
                            )
                            !=
                            action
                        ):
                            action_changes += 1

                        last_actions[
                            ticker
                        ] = action

                    pre_trade_value = (
                        capital
                    )

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

                        target_value = (
                            pre_trade_value
                            *
                            target_weights.get(
                                ticker,
                                0.0
                            )
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

    equity = pd.Series(
        equity_points
    ).sort_index()

    if equity.empty:
        return None

    spy_start = safe_float(
        spy.loc[
            trading_dates[0]
        ]
    )

    spy_equity = (
        spy.reindex(
            equity.index
        )
        /
        spy_start
        *
        STARTING_CAPITAL
    )

    metrics = calculate_equity_metrics(
        equity,
        spy_equity,
        total_trading_costs,
        turnover_notional,
        STARTING_CAPITAL
    )

    returns = (
        equity
        .pct_change()
        .dropna()
    )

    return {
        "metrics":
        metrics,

        "equity_series":
        equity,

        "daily_returns":
        returns,

        "rebalance_count":
        rebalance_count,

        "action_change_count":
        action_changes
    }


def drawdown_reduction_ratio(
    policy_metrics,
    control_metrics
):
    policy_dd = safe_float(
        policy_metrics.get(
            "max_drawdown_pct"
        ),
        0
    )

    control_dd = safe_float(
        control_metrics.get(
            "max_drawdown_pct"
        ),
        0
    )

    if control_dd <= 0:
        return 0.0

    return (
        control_dd
        -
        policy_dd
    ) / control_dd


def training_score(
    policy_metrics,
    control_metrics
):
    cagr_gap = (
        safe_float(
            policy_metrics.get(
                "cagr_pct"
            )
        )
        -
        safe_float(
            control_metrics.get(
                "cagr_pct"
            )
        )
    )

    dd_improvement = (
        safe_float(
            control_metrics.get(
                "max_drawdown_pct"
            )
        )
        -
        safe_float(
            policy_metrics.get(
                "max_drawdown_pct"
            )
        )
    )

    sharpe_improvement = (
        safe_float(
            policy_metrics.get(
                "sharpe_ratio"
            )
        )
        -
        safe_float(
            control_metrics.get(
                "sharpe_ratio"
            )
        )
    )

    return round(
        cagr_gap
        +
        0.50
        *
        dd_improvement
        +
        5.0
        *
        sharpe_improvement,
        3
    )


def select_policy_on_training_window(
    close_frame,
    tickers,
    train_start,
    train_end
):
    control = simulate_range(
        close_frame,
        tickers,
        train_start,
        train_end,
        equal_weight=True
    )

    if control is None:
        return None

    control_metrics = (
        control.get(
            "metrics",
            {}
        )
        or
        {}
    )

    candidates = []

    for name, policy in (
        POLICY_FAMILY.items()
    ):
        simulation = simulate_range(
            close_frame,
            tickers,
            train_start,
            train_end,
            policy=policy,
            equal_weight=False
        )

        if simulation is None:
            continue

        metrics = (
            simulation.get(
                "metrics",
                {}
            )
            or
            {}
        )

        dd_reduction = (
            drawdown_reduction_ratio(
                metrics,
                control_metrics
            )
        )

        candidates.append({
            "policy_name":
            name,

            "training_cagr_pct":
            metrics.get(
                "cagr_pct"
            ),

            "training_sharpe":
            metrics.get(
                "sharpe_ratio"
            ),

            "training_max_drawdown_pct":
            metrics.get(
                "max_drawdown_pct"
            ),

            "control_cagr_pct":
            control_metrics.get(
                "cagr_pct"
            ),

            "control_max_drawdown_pct":
            control_metrics.get(
                "max_drawdown_pct"
            ),

            "drawdown_reduction_ratio":
            round(
                dd_reduction,
                3
            ),

            "risk_constraint_pass":
            (
                dd_reduction
                >=
                MIN_DRAWDOWN_REDUCTION_RATIO
            ),

            "training_score":
            training_score(
                metrics,
                control_metrics
            )
        })

    if not candidates:
        return None

    constrained = [
        item
        for item in candidates
        if item.get(
            "risk_constraint_pass"
        )
    ]

    if constrained:
        selected = max(
            constrained,
            key=lambda item: (
                safe_float(
                    item.get(
                        "training_cagr_pct"
                    )
                ),
                safe_float(
                    item.get(
                        "training_sharpe"
                    )
                )
            )
        )

        selection_rule = (
            "Highest training CAGR among policies reducing "
            "max drawdown by at least 15% vs equal-weight control"
        )

    else:
        selected = max(
            candidates,
            key=lambda item:
            safe_float(
                item.get(
                    "training_score"
                )
            )
        )

        selection_rule = (
            "No policy met the drawdown constraint; selected highest "
            "predefined composite training score"
        )

    return {
        "selected_policy_name":
        selected.get(
            "policy_name"
        ),

        "selection_rule":
        selection_rule,

        "selected_training_result":
        selected,

        "all_training_candidates":
        sorted(
            candidates,
            key=lambda item:
            safe_float(
                item.get(
                    "training_cagr_pct"
                )
            ),
            reverse=True
        )
    }


def normalize_fold_returns(
    simulation
):
    if simulation is None:
        return pd.Series(
            dtype=float
        )

    returns = (
        simulation.get(
            "daily_returns"
        )
    )

    if returns is None:
        return pd.Series(
            dtype=float
        )

    return returns.dropna()


def metrics_from_stitched_returns(
    returns
):
    returns = returns.dropna()

    if returns.empty:
        return {}

    equity = (
        (
            1
            +
            returns
        ).cumprod()
        *
        STARTING_CAPITAL
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
        STARTING_CAPITAL
        -
        1
    )

    cagr = (
        (
            equity.iloc[-1]
            /
            STARTING_CAPITAL
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

    drawdown = (
        equity
        /
        equity.cummax()
        -
        1
    )

    max_drawdown = abs(
        safe_float(
            drawdown.min()
        )
    )

    return {
        "starting_value":
        STARTING_CAPITAL,

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


def promotion_verdict(
    calibrated_metrics,
    default_metrics,
    control_metrics,
    fold_results
):
    calibrated_cagr = safe_float(
        calibrated_metrics.get(
            "cagr_pct"
        )
    )

    default_cagr = safe_float(
        default_metrics.get(
            "cagr_pct"
        )
    )

    control_cagr = safe_float(
        control_metrics.get(
            "cagr_pct"
        )
    )

    calibrated_sharpe = safe_float(
        calibrated_metrics.get(
            "sharpe_ratio"
        )
    )

    default_sharpe = safe_float(
        default_metrics.get(
            "sharpe_ratio"
        )
    )

    calibrated_dd = safe_float(
        calibrated_metrics.get(
            "max_drawdown_pct"
        )
    )

    control_dd = safe_float(
        control_metrics.get(
            "max_drawdown_pct"
        )
    )

    fold_wins_default = sum(
        1
        for fold in fold_results
        if safe_float(
            fold.get(
                "calibrated_vs_default_pct"
            )
        )
        >
        0
    )

    fold_wins_control = sum(
        1
        for fold in fold_results
        if safe_float(
            fold.get(
                "calibrated_vs_control_pct"
            )
        )
        >
        0
    )

    fold_count = len(
        fold_results
    )

    criteria = {
        "cagr_improvement_vs_default_pct":
        round(
            calibrated_cagr
            -
            default_cagr,
            2
        ),

        "cagr_gap_vs_control_pct":
        round(
            calibrated_cagr
            -
            control_cagr,
            2
        ),

        "sharpe_improvement_vs_default":
        round(
            calibrated_sharpe
            -
            default_sharpe,
            3
        ),

        "drawdown_reduction_vs_control_pct":
        round(
            control_dd
            -
            calibrated_dd,
            2
        ),

        "fold_win_rate_vs_default_pct":
        (
            round(
                fold_wins_default
                /
                fold_count
                *
                100,
                1
            )
            if fold_count
            else 0
        ),

        "fold_win_rate_vs_control_pct":
        (
            round(
                fold_wins_control
                /
                fold_count
                *
                100,
                1
            )
            if fold_count
            else 0
        )
    }

    promote = (
        criteria[
            "cagr_improvement_vs_default_pct"
        ]
        >=
        3.0
        and
        criteria[
            "sharpe_improvement_vs_default"
        ]
        >=
        0.05
        and
        criteria[
            "drawdown_reduction_vs_control_pct"
        ]
        >=
        5.0
        and
        criteria[
            "fold_win_rate_vs_default_pct"
        ]
        >=
        60.0
        and
        criteria[
            "cagr_gap_vs_control_pct"
        ]
        >=
        -8.0
    )

    if promote:
        return {
            "status":
            "PROMOTE_CANDIDATE",

            "message":
            (
                "Calibrated policy materially improves the live default "
                "out-of-sample while retaining meaningful drawdown protection."
            ),

            "criteria":
            criteria
        }

    return {
        "status":
        "KEEP_DEFAULT",

        "message":
        (
            "Calibration evidence is not strong enough to replace the live "
            "V7.9 policy. Keep the current live policy unchanged and use "
            "the lab result for further research."
        ),

        "criteria":
        criteria
    }


def run_strategic_policy_calibration(
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

    all_tickers = (
        tickers
        +
        [
            "SPY"
        ]
    )

    close_frame = download_close_history(
        all_tickers
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

            "calibration_signature":
            CALIBRATION_SIGNATURE,

            "status":
            "NO_DATA",

            "generated":
            datetime.now(
                timezone.utc
            ).isoformat()
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

            "calibration_signature":
            CALIBRATION_SIGNATURE,

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

    spy_dates = [
        date_value
        for date_value in (
            close_frame[
                "SPY"
            ].dropna().index
        )
        if date_value >= start_date
    ]

    if (
        len(
            spy_dates
        )
        <
        (
            TRAINING_SESSIONS_MIN
            +
            80
        )
    ):
        result = {
            "engine":
            ENGINE_VERSION,

            "calibration_signature":
            CALIBRATION_SIGNATURE,

            "portfolio_signature":
            signature,

            "market_date":
            market_date,

            "status":
            "INSUFFICIENT_CALIBRATION_WINDOW",

            "generated":
            datetime.now(
                timezone.utc
            ).isoformat()
        }

        save_result(
            result
        )

        return result

    fold_results = []

    stitched_calibrated = []

    stitched_default = []

    stitched_control = []

    policy_selection_counts = {
        name:
        0
        for name in POLICY_FAMILY
    }

    oos_start_index = (
        TRAINING_SESSIONS_MIN
    )

    fold_number = 1

    while (
        oos_start_index
        <
        len(
            spy_dates
        )
        -
        40
    ):
        oos_end_index = min(
            oos_start_index
            +
            OOS_FOLD_SESSIONS
            -
            1,
            len(
                spy_dates
            )
            -
            1
        )

        if (
            oos_end_index
            -
            oos_start_index
        )
        <
        40:
            break

        train_start = spy_dates[
            0
        ]

        train_end = spy_dates[
            oos_start_index
            -
            1
        ]

        oos_start = spy_dates[
            oos_start_index
        ]

        oos_end = spy_dates[
            oos_end_index
        ]

        selection = (
            select_policy_on_training_window(
                close_frame,
                tickers,
                train_start,
                train_end
            )
        )

        if selection is None:
            break

        selected_name = (
            selection.get(
                "selected_policy_name"
            )
        )

        selected_policy = (
            POLICY_FAMILY.get(
                selected_name
            )
        )

        if selected_policy is None:
            break

        policy_selection_counts[
            selected_name
        ] += 1

        calibrated_sim = simulate_range(
            close_frame,
            tickers,
            oos_start,
            oos_end,
            policy=selected_policy,
            equal_weight=False
        )

        default_sim = simulate_range(
            close_frame,
            tickers,
            oos_start,
            oos_end,
            policy=POLICY_FAMILY[
                "DEFAULT_V7_9"
            ],
            equal_weight=False
        )

        control_sim = simulate_range(
            close_frame,
            tickers,
            oos_start,
            oos_end,
            equal_weight=True
        )

        if (
            calibrated_sim is None
            or
            default_sim is None
            or
            control_sim is None
        ):
            break

        calibrated_metrics = (
            calibrated_sim.get(
                "metrics",
                {}
            )
            or
            {}
        )

        default_metrics = (
            default_sim.get(
                "metrics",
                {}
            )
            or
            {}
        )

        control_metrics = (
            control_sim.get(
                "metrics",
                {}
            )
            or
            {}
        )

        calibrated_return = safe_float(
            calibrated_metrics.get(
                "total_return_pct"
            )
        )

        default_return = safe_float(
            default_metrics.get(
                "total_return_pct"
            )
        )

        control_return = safe_float(
            control_metrics.get(
                "total_return_pct"
            )
        )

        fold_results.append({
            "fold":
            fold_number,

            "train_start":
            str(
                train_start.date()
            ),

            "train_end":
            str(
                train_end.date()
            ),

            "oos_start":
            str(
                oos_start.date()
            ),

            "oos_end":
            str(
                oos_end.date()
            ),

            "selected_policy":
            selected_name,

            "selection_rule":
            selection.get(
                "selection_rule"
            ),

            "selected_training_result":
            selection.get(
                "selected_training_result"
            ),

            "oos_calibrated_return_pct":
            round(
                calibrated_return,
                2
            ),

            "oos_default_return_pct":
            round(
                default_return,
                2
            ),

            "oos_control_return_pct":
            round(
                control_return,
                2
            ),

            "calibrated_vs_default_pct":
            round(
                calibrated_return
                -
                default_return,
                2
            ),

            "calibrated_vs_control_pct":
            round(
                calibrated_return
                -
                control_return,
                2
            ),

            "calibrated_max_drawdown_pct":
            calibrated_metrics.get(
                "max_drawdown_pct"
            ),

            "default_max_drawdown_pct":
            default_metrics.get(
                "max_drawdown_pct"
            ),

            "control_max_drawdown_pct":
            control_metrics.get(
                "max_drawdown_pct"
            ),

            "calibrated_sharpe":
            calibrated_metrics.get(
                "sharpe_ratio"
            ),

            "default_sharpe":
            default_metrics.get(
                "sharpe_ratio"
            )
        })

        stitched_calibrated.append(
            normalize_fold_returns(
                calibrated_sim
            )
        )

        stitched_default.append(
            normalize_fold_returns(
                default_sim
            )
        )

        stitched_control.append(
            normalize_fold_returns(
                control_sim
            )
        )

        oos_start_index = (
            oos_end_index
            +
            1
        )

        fold_number += 1

    if not fold_results:
        result = {
            "engine":
            ENGINE_VERSION,

            "calibration_signature":
            CALIBRATION_SIGNATURE,

            "portfolio_signature":
            signature,

            "market_date":
            market_date,

            "status":
            "NO_VALID_OOS_FOLDS",

            "generated":
            datetime.now(
                timezone.utc
            ).isoformat()
        }

        save_result(
            result
        )

        return result

    calibrated_returns = pd.concat(
        stitched_calibrated
    ).sort_index()

    default_returns = pd.concat(
        stitched_default
    ).sort_index()

    control_returns = pd.concat(
        stitched_control
    ).sort_index()

    calibrated_metrics = (
        metrics_from_stitched_returns(
            calibrated_returns
        )
    )

    default_metrics = (
        metrics_from_stitched_returns(
            default_returns
        )
    )

    control_metrics = (
        metrics_from_stitched_returns(
            control_returns
        )
    )

    verdict = promotion_verdict(
        calibrated_metrics,
        default_metrics,
        control_metrics,
        fold_results
    )

    most_selected_policy = max(
        policy_selection_counts,
        key=lambda name:
        policy_selection_counts[
            name
        ]
    )

    result = {
        "engine":
        ENGINE_VERSION,

        "calibration_signature":
        CALIBRATION_SIGNATURE,

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

        "live_policy_status":
        "V7.9 DEFAULT UNCHANGED",

        "validation_scope":
        "CURRENT_PORTFOLIO_STRATEGIC_PRICE_RISK_LAYER",

        "methodology": {
            "policy_family_size":
            len(
                POLICY_FAMILY
            ),

            "policy_family":
            list(
                POLICY_FAMILY.keys()
            ),

            "training_mode":
            "EXPANDING_WINDOW",

            "minimum_training_sessions":
            TRAINING_SESSIONS_MIN,

            "oos_fold_sessions":
            OOS_FOLD_SESSIONS,

            "selection_constraint":
            (
                "Prefer highest CAGR among predefined policies that reduce "
                "training max drawdown by at least 15% vs same-universe "
                "equal-weight control."
            ),

            "execution":
            (
                "Prior-session data only; selected policy frozen for the "
                "entire next out-of-sample fold."
            ),

            "parameter_search":
            "SMALL_PREDECLARED_POLICY_FAMILY_ONLY",

            "automatic_live_promotion":
            False
        },

        "policy_family":
        POLICY_FAMILY,

        "policy_selection_counts":
        policy_selection_counts,

        "most_selected_policy":
        most_selected_policy,

        "out_of_sample": {
            "fold_count":
            len(
                fold_results
            ),

            "calibrated_policy":
            calibrated_metrics,

            "default_v7_9":
            default_metrics,

            "equal_weight_control":
            control_metrics,

            "folds":
            fold_results
        },

        "promotion_verdict":
        verdict,

        "limitations": [
            (
                "The universe is the current portfolio, so survivorship and "
                "selection bias remain."
            ),
            (
                "Historical news, fundamentals, events and sector-state "
                "snapshots are not reconstructed."
            ),
            (
                "Only five predeclared policy families are compared to reduce "
                "data-mining risk; this is not exhaustive optimization."
            ),
            (
                "A PROMOTE_CANDIDATE verdict would still require a separate "
                "live-policy review before changing V7.9 thresholds."
            )
        ]
    }

    save_result(
        result
    )

    return result
