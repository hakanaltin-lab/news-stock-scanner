"""
V8.4.6 AURORA Regime Failure Attribution & Shadow Calibration

Purpose:
- Explain why the live/default strategic overlay underperforms in V8.4.5
  RISK_OFF and HIGH_VOL regimes.
- Reuse only the predeclared V8.1 policy family and the policy that was
  selected using prior training history for each historical OOS fold.
- Measure whether the already-existing shadow behavior repairs those weak
  regimes without changing live V7.9 policy thresholds.
- Attribute live-vs-shadow exposure divergences, especially REDUCE/EXIT,
  to subsequent 20-session benchmark-relative outcomes.

Important:
- This is diagnostic and shadow-only.
- No new thresholds are optimized here.
- No broker orders are sent.
- Live V7.9 policy remains unchanged.
"""

from datetime import datetime, timezone
import hashlib
import json
import math
import os

import numpy as np
import pandas as pd

from engines.strategic_policy_calibration_engine import (
    POLICY_FAMILY,
    REBALANCE_EVERY_SESSIONS,
    build_policy_target_weights,
    download_close_history,
    policy_exposure,
    previous_trading_date,
    safe_float,
    simulate_range
)


ENGINE_VERSION = (
    "V8.4.6 Regime Failure Attribution & Shadow Calibration"
)

ATTRIBUTION_SIGNATURE = "V8.4.6"

OUTPUT_FILE = "docs/regime_failure_attribution.json"

TREND_LOOKBACK_SESSIONS = 63

SHORT_VOL_SESSIONS = 21

LONG_VOL_SESSIONS = 126

FORWARD_EVALUATION_SESSIONS = 20

MIN_DIVERGENCE = 0.05


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
    market_date,
    calibration_signature,
    backtest_signature
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
                "attribution_signature"
            )
            !=
            ATTRIBUTION_SIGNATURE
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

        if (
            data.get(
                "source_calibration_signature"
            )
            !=
            calibration_signature
        ):
            return None

        if (
            data.get(
                "source_backtest_signature"
            )
            !=
            backtest_signature
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


def parse_date(value):
    try:
        return pd.Timestamp(
            value
        )
    except Exception:
        return None


def annualized_return(
    returns
):
    clean = (
        returns
        .replace(
            [np.inf, -np.inf],
            np.nan
        )
        .dropna()
    )

    if clean.empty:
        return None

    gross = (
        1.0
        +
        clean.to_numpy(
            dtype=float
        )
    )

    if np.any(
        gross
        <=
        0
    ):
        return None

    return (
        math.exp(
            safe_float(
                np.log(
                    gross
                ).mean(),
                0.0
            )
            *
            252
        )
        -
        1.0
    ) * 100


def sharpe_ratio(
    returns
):
    clean = (
        returns
        .replace(
            [np.inf, -np.inf],
            np.nan
        )
        .dropna()
    )

    if len(
        clean
    ) < 2:
        return None

    std = safe_float(
        clean.std(),
        0.0
    )

    if std <= 0:
        return None

    return (
        safe_float(
            clean.mean(),
            0.0
        )
        /
        std
        *
        math.sqrt(
            252
        )
    )


def max_drawdown_pct(
    returns
):
    clean = (
        returns
        .replace(
            [np.inf, -np.inf],
            np.nan
        )
        .dropna()
    )

    if clean.empty:
        return None

    compounded = (
        (
            1.0
            +
            clean
        )
        .cumprod()
        .to_numpy(
            dtype=float
        )
    )

    values = np.concatenate(
        (
            np.array(
                [1.0],
                dtype=float
            ),
            compounded
        )
    )

    running_max = (
        np.maximum.accumulate(
            values
        )
    )

    drawdown = (
        values
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


def summarize_pair(
    default_returns,
    shadow_returns
):
    pair = pd.concat(
        [
            default_returns.rename(
                "default"
            ),
            shadow_returns.rename(
                "shadow"
            )
        ],
        axis=1,
        join="inner"
    ).replace(
        [np.inf, -np.inf],
        np.nan
    ).dropna()

    if pair.empty:
        return {
            "sessions":
            0
        }

    default_ann = annualized_return(
        pair[
            "default"
        ]
    )

    shadow_ann = annualized_return(
        pair[
            "shadow"
        ]
    )

    default_sharpe = sharpe_ratio(
        pair[
            "default"
        ]
    )

    shadow_sharpe = sharpe_ratio(
        pair[
            "shadow"
        ]
    )

    default_dd = max_drawdown_pct(
        pair[
            "default"
        ]
    )

    shadow_dd = max_drawdown_pct(
        pair[
            "shadow"
        ]
    )

    relative_wealth = (
        (
            1.0
            +
            pair[
                "shadow"
            ]
        ).prod()
        /
        (
            1.0
            +
            pair[
                "default"
            ]
        ).prod()
        -
        1.0
    ) * 100

    return {
        "sessions":
        len(
            pair
        ),

        "start_date":
        str(
            pair.index[
                0
            ].date()
        ),

        "end_date":
        str(
            pair.index[
                -1
            ].date()
        ),

        "default_annualized_return_pct":
        (
            round(
                default_ann,
                2
            )
            if default_ann is not None
            else None
        ),

        "shadow_annualized_return_pct":
        (
            round(
                shadow_ann,
                2
            )
            if shadow_ann is not None
            else None
        ),

        "shadow_return_advantage_pct_points":
        (
            round(
                shadow_ann
                -
                default_ann,
                2
            )
            if (
                shadow_ann is not None
                and
                default_ann is not None
            )
            else None
        ),

        "default_sharpe":
        (
            round(
                default_sharpe,
                3
            )
            if default_sharpe is not None
            else None
        ),

        "shadow_sharpe":
        (
            round(
                shadow_sharpe,
                3
            )
            if shadow_sharpe is not None
            else None
        ),

        "shadow_sharpe_advantage":
        (
            round(
                shadow_sharpe
                -
                default_sharpe,
                3
            )
            if (
                shadow_sharpe is not None
                and
                default_sharpe is not None
            )
            else None
        ),

        "default_max_drawdown_pct":
        (
            round(
                default_dd,
                2
            )
            if default_dd is not None
            else None
        ),

        "shadow_max_drawdown_pct":
        (
            round(
                shadow_dd,
                2
            )
            if shadow_dd is not None
            else None
        ),

        "shadow_drawdown_advantage_pct":
        (
            round(
                default_dd
                -
                shadow_dd,
                2
            )
            if (
                default_dd is not None
                and
                shadow_dd is not None
            )
            else None
        ),

        "shadow_relative_wealth_advantage_pct":
        round(
            safe_float(
                relative_wealth,
                0.0
            ),
            2
        )
    }


def build_regime_series(
    spy
):
    spy = (
        spy
        .dropna()
        .astype(
            float
        )
    )

    returns = (
        spy
        .pct_change()
        .replace(
            [np.inf, -np.inf],
            np.nan
        )
    )

    trend = (
        spy
        .pct_change(
            TREND_LOOKBACK_SESSIONS
        )
        .shift(
            1
        )
    )

    short_vol = (
        returns
        .rolling(
            SHORT_VOL_SESSIONS,
            min_periods=max(
                10,
                SHORT_VOL_SESSIONS // 2
            )
        )
        .std()
        .shift(
            1
        )
        *
        math.sqrt(
            252
        )
    )

    long_vol = (
        returns
        .rolling(
            LONG_VOL_SESSIONS,
            min_periods=max(
                40,
                LONG_VOL_SESSIONS // 2
            )
        )
        .std()
        .shift(
            1
        )
        *
        math.sqrt(
            252
        )
    )

    return pd.DataFrame({
        "trend_return_63":
        trend,

        "short_vol":
        short_vol,

        "long_vol":
        long_vol,

        "risk_off":
        trend
        <
        0,

        "high_vol":
        short_vol
        >
        long_vol
    })


def regime_labels(
    regime_frame,
    date_value
):
    if (
        date_value
        not in regime_frame.index
    ):
        return (
            None,
            None
        )

    row = regime_frame.loc[
        date_value
    ]

    trend_regime = (
        "RISK_OFF"
        if row.get(
            "risk_off"
        )
        is True
        or
        row.get(
            "risk_off"
        )
        ==
        True
        else
        "RISK_ON"
    )

    volatility_regime = (
        "HIGH_VOL"
        if row.get(
            "high_vol"
        )
        is True
        or
        row.get(
            "high_vol"
        )
        ==
        True
        else
        "LOWER_VOL"
    )

    return (
        trend_regime,
        volatility_regime
    )


def summarize_events(
    events
):
    evaluated = [
        item
        for item in events
        if item.get(
            "evaluated"
        )
        is True
    ]

    if not events:
        return {
            "records":
            0,

            "evaluated":
            0,

            "pending":
            0,

            "shadow_hit_rate_pct":
            None,

            "average_shadow_relative_alpha_20d_pct":
            None,

            "average_exposure_difference":
            None
        }

    exposure_values = [
        safe_float(
            item.get(
                "exposure_difference"
            ),
            0.0
        )
        for item in events
    ]

    alpha_values = [
        safe_float(
            item.get(
                "shadow_relative_alpha_20d_pct"
            ),
            0.0
        )
        for item in evaluated
        if item.get(
            "shadow_relative_alpha_20d_pct"
        )
        is not None
    ]

    hits = sum(
        1
        for item in evaluated
        if item.get(
            "shadow_hit"
        )
        is True
    )

    return {
        "records":
        len(
            events
        ),

        "evaluated":
        len(
            evaluated
        ),

        "pending":
        len(
            events
        )
        -
        len(
            evaluated
        ),

        "shadow_hit_rate_pct":
        (
            round(
                hits
                /
                len(
                    evaluated
                )
                *
                100,
                1
            )
            if evaluated
            else None
        ),

        "average_shadow_relative_alpha_20d_pct":
        (
            round(
                sum(
                    alpha_values
                )
                /
                len(
                    alpha_values
                ),
                3
            )
            if alpha_values
            else None
        ),

        "average_exposure_difference":
        round(
            sum(
                exposure_values
            )
            /
            len(
                exposure_values
            ),
            3
        ),

        "more_exposure_records":
        sum(
            1
            for value in exposure_values
            if value
            >
            0
        ),

        "less_exposure_records":
        sum(
            1
            for value in exposure_values
            if value
            <
            0
        )
    }


def run_regime_failure_attribution(
    portfolio_rows,
    walk_forward_result,
    calibration_result,
    force=False
):
    walk_forward_result = (
        walk_forward_result
        or
        {}
    )

    calibration_result = (
        calibration_result
        or
        {}
    )

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

    if not tickers:
        result = {
            "engine":
            ENGINE_VERSION,

            "attribution_signature":
            ATTRIBUTION_SIGNATURE,

            "status":
            "NO_PORTFOLIO",

            "live_policy_changed":
            False,

            "live_execution_authorized":
            False
        }

        save_result(
            result
        )

        return result

    folds = (
        (
            calibration_result.get(
                "out_of_sample",
                {}
            )
            or
            {}
        ).get(
            "folds",
            []
        )
        or
        []
    )

    if not folds:
        result = {
            "engine":
            ENGINE_VERSION,

            "attribution_signature":
            ATTRIBUTION_SIGNATURE,

            "status":
            "NO_OOS_FOLDS",

            "live_policy_changed":
            False,

            "live_execution_authorized":
            False
        }

        save_result(
            result
        )

        return result

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

            "attribution_signature":
            ATTRIBUTION_SIGNATURE,

            "status":
            "NO_DATA",

            "live_policy_changed":
            False,

            "live_execution_authorized":
            False
        }

        save_result(
            result
        )

        return result

    spy = (
        close_frame[
            "SPY"
        ].dropna()
    )

    market_date = str(
        spy.index[
            -1
        ].date()
    )

    signature = portfolio_signature(
        tickers
    )

    calibration_signature = (
        calibration_result.get(
            "calibration_signature"
        )
    )

    backtest_signature = (
        walk_forward_result.get(
            "backtest_signature"
        )
    )

    if not force:
        cached = load_cached_result(
            signature,
            market_date,
            calibration_signature,
            backtest_signature
        )

        if cached is not None:
            return cached

    regime_frame = build_regime_series(
        spy
    )

    stitched_default = []

    stitched_shadow = []

    fold_diagnostics = []

    divergence_events = []

    all_spy_dates = list(
        spy.index
    )

    for fold in folds:
        fold_start = parse_date(
            fold.get(
                "oos_start"
            )
        )

        fold_end = parse_date(
            fold.get(
                "oos_end"
            )
        )

        selected_name = fold.get(
            "selected_policy"
        )

        selected_policy = (
            POLICY_FAMILY.get(
                selected_name
            )
        )

        default_policy = (
            POLICY_FAMILY.get(
                "DEFAULT_V7_9"
            )
        )

        if (
            fold_start is None
            or
            fold_end is None
            or
            selected_policy is None
            or
            default_policy is None
        ):
            continue

        shadow_sim = simulate_range(
            close_frame,
            tickers,
            fold_start,
            fold_end,
            policy=selected_policy,
            equal_weight=False
        )

        default_sim = simulate_range(
            close_frame,
            tickers,
            fold_start,
            fold_end,
            policy=default_policy,
            equal_weight=False
        )

        if (
            shadow_sim is None
            or
            default_sim is None
        ):
            continue

        shadow_returns = (
            shadow_sim.get(
                "daily_returns"
            )
        )

        default_returns = (
            default_sim.get(
                "daily_returns"
            )
        )

        if (
            shadow_returns is None
            or
            default_returns is None
        ):
            continue

        pair = pd.concat(
            [
                default_returns.rename(
                    "default"
                ),
                shadow_returns.rename(
                    "shadow"
                )
            ],
            axis=1,
            join="inner"
        ).dropna()

        if pair.empty:
            continue

        stitched_default.append(
            pair[
                "default"
            ]
        )

        stitched_shadow.append(
            pair[
                "shadow"
            ]
        )

        fold_summary = summarize_pair(
            pair[
                "default"
            ],
            pair[
                "shadow"
            ]
        )

        fold_summary[
            "fold"
        ] = fold.get(
            "fold"
        )

        fold_summary[
            "selected_policy"
        ] = selected_name

        fold_diagnostics.append(
            fold_summary
        )

        fold_execution_dates = [
            date_value
            for date_value in all_spy_dates
            if (
                date_value
                >=
                fold_start
                and
                date_value
                <=
                fold_end
            )
        ]

        for index, execution_date in enumerate(
            fold_execution_dates
        ):
            if (
                index
                !=
                0
                and
                index
                %
                REBALANCE_EVERY_SESSIONS
                !=
                0
            ):
                continue

            decision_date = previous_trading_date(
                all_spy_dates,
                execution_date
            )

            if decision_date is None:
                continue

            (
                default_weights,
                default_states
            ) = build_policy_target_weights(
                decision_date,
                tickers,
                close_frame,
                default_policy
            )

            (
                shadow_weights,
                shadow_states
            ) = build_policy_target_weights(
                decision_date,
                tickers,
                close_frame,
                selected_policy
            )

            if (
                not default_weights
                or
                not shadow_weights
            ):
                continue

            trend_regime, volatility_regime = (
                regime_labels(
                    regime_frame,
                    execution_date
                )
            )

            future_dates = [
                date_value
                for date_value in all_spy_dates
                if date_value
                >
                execution_date
            ]

            evaluation_date = (
                future_dates[
                    FORWARD_EVALUATION_SESSIONS
                    -
                    1
                ]
                if len(
                    future_dates
                )
                >=
                FORWARD_EVALUATION_SESSIONS
                else None
            )

            for ticker in tickers:
                default_state = (
                    default_states.get(
                        ticker,
                        {}
                    )
                    or
                    {}
                )

                shadow_state = (
                    shadow_states.get(
                        ticker,
                        {}
                    )
                    or
                    {}
                )

                default_action = (
                    default_state.get(
                        "action"
                    )
                )

                shadow_action = (
                    shadow_state.get(
                        "action"
                    )
                )

                if (
                    default_action is None
                    or
                    shadow_action is None
                ):
                    continue

                default_exposure = policy_exposure(
                    default_action,
                    default_policy
                )

                shadow_exposure = policy_exposure(
                    shadow_action,
                    selected_policy
                )

                exposure_difference = (
                    shadow_exposure
                    -
                    default_exposure
                )

                if abs(
                    exposure_difference
                ) < MIN_DIVERGENCE:
                    continue

                event = {
                    "fold":
                    fold.get(
                        "fold"
                    ),

                    "selected_policy":
                    selected_name,

                    "ticker":
                    ticker,

                    "decision_date":
                    str(
                        decision_date.date()
                    ),

                    "execution_date":
                    str(
                        execution_date.date()
                    ),

                    "trend_regime":
                    trend_regime,

                    "volatility_regime":
                    volatility_regime,

                    "default_action":
                    default_action,

                    "shadow_action":
                    shadow_action,

                    "default_exposure":
                    round(
                        default_exposure,
                        2
                    ),

                    "shadow_exposure":
                    round(
                        shadow_exposure,
                        2
                    ),

                    "exposure_difference":
                    round(
                        exposure_difference,
                        2
                    ),

                    "direction":
                    (
                        "MORE_EXPOSURE"
                        if exposure_difference
                        >
                        0
                        else
                        "LESS_EXPOSURE"
                    ),

                    "default_defensive_action":
                    default_action
                    in [
                        "REDUCE",
                        "EXIT"
                    ],

                    "evaluated":
                    False,

                    "evaluation_date":
                    (
                        str(
                            evaluation_date.date()
                        )
                        if evaluation_date is not None
                        else None
                    ),

                    "stock_excess_return_20d_pct":
                    None,

                    "shadow_relative_alpha_20d_pct":
                    None,

                    "shadow_hit":
                    None
                }

                if (
                    evaluation_date is not None
                    and
                    ticker
                    in
                    close_frame.columns
                ):
                    try:
                        stock_entry = safe_float(
                            close_frame.loc[
                                execution_date,
                                ticker
                            ],
                            0.0
                        )

                        stock_future = safe_float(
                            close_frame.loc[
                                evaluation_date,
                                ticker
                            ],
                            0.0
                        )

                        spy_entry = safe_float(
                            spy.loc[
                                execution_date
                            ],
                            0.0
                        )

                        spy_future = safe_float(
                            spy.loc[
                                evaluation_date
                            ],
                            0.0
                        )

                        if min(
                            stock_entry,
                            stock_future,
                            spy_entry,
                            spy_future
                        ) > 0:
                            stock_return = (
                                stock_future
                                /
                                stock_entry
                                -
                                1.0
                            ) * 100

                            spy_return = (
                                spy_future
                                /
                                spy_entry
                                -
                                1.0
                            ) * 100

                            excess_return = (
                                stock_return
                                -
                                spy_return
                            )

                            shadow_alpha = (
                                exposure_difference
                                *
                                excess_return
                            )

                            event.update({
                                "evaluated":
                                True,

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

                                "stock_excess_return_20d_pct":
                                round(
                                    excess_return,
                                    2
                                ),

                                "shadow_relative_alpha_20d_pct":
                                round(
                                    shadow_alpha,
                                    3
                                ),

                                "shadow_hit":
                                shadow_alpha
                                >
                                0
                            })

                    except Exception:
                        pass

                divergence_events.append(
                    event
                )

    if (
        not stitched_default
        or
        not stitched_shadow
    ):
        result = {
            "engine":
            ENGINE_VERSION,

            "attribution_signature":
            ATTRIBUTION_SIGNATURE,

            "portfolio_signature":
            signature,

            "market_date":
            market_date,

            "status":
            "NO_VALID_OOS_REPLAY",

            "live_policy_changed":
            False,

            "live_execution_authorized":
            False
        }

        save_result(
            result
        )

        return result

    default_returns = pd.concat(
        stitched_default
    ).sort_index()

    shadow_returns = pd.concat(
        stitched_shadow
    ).sort_index()

    pair = pd.concat(
        [
            default_returns.rename(
                "default"
            ),
            shadow_returns.rename(
                "shadow"
            )
        ],
        axis=1,
        join="inner"
    ).dropna()

    regime_results = {}

    masks = {
        "RISK_ON":
        regime_frame[
            "risk_off"
        ]
        ==
        False,

        "RISK_OFF":
        regime_frame[
            "risk_off"
        ]
        ==
        True,

        "HIGH_VOL":
        regime_frame[
            "high_vol"
        ]
        ==
        True,

        "LOWER_VOL":
        regime_frame[
            "high_vol"
        ]
        ==
        False
    }

    for name, mask in masks.items():
        dates = mask[
            mask.fillna(
                False
            )
        ].index

        regime_pair = pair.loc[
            pair.index.intersection(
                dates
            )
        ]

        regime_results[
            name
        ] = summarize_pair(
            regime_pair[
                "default"
            ],
            regime_pair[
                "shadow"
            ]
        )

    event_groups = {
        "ALL_DIVERGENCES":
        divergence_events,

        "RISK_OFF":
        [
            item
            for item in divergence_events
            if item.get(
                "trend_regime"
            )
            ==
            "RISK_OFF"
        ],

        "HIGH_VOL":
        [
            item
            for item in divergence_events
            if item.get(
                "volatility_regime"
            )
            ==
            "HIGH_VOL"
        ],

        "DEFAULT_REDUCE_EXIT_MORE_EXPOSURE":
        [
            item
            for item in divergence_events
            if (
                item.get(
                    "default_defensive_action"
                )
                is True
                and
                safe_float(
                    item.get(
                        "exposure_difference"
                    ),
                    0.0
                )
                >
                0
            )
        ],

        "RISK_OFF_DEFAULT_REDUCE_EXIT_MORE_EXPOSURE":
        [
            item
            for item in divergence_events
            if (
                item.get(
                    "trend_regime"
                )
                ==
                "RISK_OFF"
                and
                item.get(
                    "default_defensive_action"
                )
                is True
                and
                safe_float(
                    item.get(
                        "exposure_difference"
                    ),
                    0.0
                )
                >
                0
            )
        ],

        "HIGH_VOL_DEFAULT_REDUCE_EXIT_MORE_EXPOSURE":
        [
            item
            for item in divergence_events
            if (
                item.get(
                    "volatility_regime"
                )
                ==
                "HIGH_VOL"
                and
                item.get(
                    "default_defensive_action"
                )
                is True
                and
                safe_float(
                    item.get(
                        "exposure_difference"
                    ),
                    0.0
                )
                >
                0
            )
        ]
    }

    event_summary = {
        name:
        summarize_events(
            events
        )
        for name, events in (
            event_groups.items()
        )
    }

    by_default_action = {}

    for action in [
        "HOLD",
        "WATCH",
        "REDUCE",
        "EXIT"
    ]:
        by_default_action[
            action
        ] = summarize_events(
            [
                item
                for item in divergence_events
                if item.get(
                    "default_action"
                )
                ==
                action
            ]
        )

    risk_off_repair = safe_float(
        (
            regime_results.get(
                "RISK_OFF",
                {}
            )
            or
            {}
        ).get(
            "shadow_return_advantage_pct_points"
        ),
        0.0
    )

    high_vol_repair = safe_float(
        (
            regime_results.get(
                "HIGH_VOL",
                {}
            )
            or
            {}
        ).get(
            "shadow_return_advantage_pct_points"
        ),
        0.0
    )

    defensive_alpha = safe_float(
        (
            event_summary.get(
                "DEFAULT_REDUCE_EXIT_MORE_EXPOSURE",
                {}
            )
            or
            {}
        ).get(
            "average_shadow_relative_alpha_20d_pct"
        ),
        0.0
    )

    risk_off_defensive_alpha = safe_float(
        (
            event_summary.get(
                "RISK_OFF_DEFAULT_REDUCE_EXIT_MORE_EXPOSURE",
                {}
            )
            or
            {}
        ).get(
            "average_shadow_relative_alpha_20d_pct"
        ),
        0.0
    )

    high_vol_defensive_alpha = safe_float(
        (
            event_summary.get(
                "HIGH_VOL_DEFAULT_REDUCE_EXIT_MORE_EXPOSURE",
                {}
            )
            or
            {}
        ).get(
            "average_shadow_relative_alpha_20d_pct"
        ),
        0.0
    )

    if (
        risk_off_repair
        >
        0
        and
        high_vol_repair
        >
        0
        and
        defensive_alpha
        >
        0
    ):
        primary_failure_mode = (
            "OVER_DEFENSIVE_EXPOSURE_CUTS_AND_REBOUND_COST"
        )

    elif (
        risk_off_repair
        >
        0
        and
        risk_off_defensive_alpha
        >
        0
    ):
        primary_failure_mode = (
            "RISK_OFF_EARLY_DERISKING_REBOUND_COST"
        )

    elif (
        high_vol_repair
        >
        0
        and
        high_vol_defensive_alpha
        >
        0
    ):
        primary_failure_mode = (
            "HIGH_VOL_EXPOSURE_CALIBRATION_COST"
        )

    elif (
        risk_off_repair
        >
        0
        or
        high_vol_repair
        >
        0
    ):
        primary_failure_mode = (
            "PARTIAL_REGIME_REPAIR_NOT_ACTION_SPECIFIC"
        )

    else:
        primary_failure_mode = (
            "EXISTING_SHADOW_POLICY_DOES_NOT_REPAIR_WEAK_REGIMES"
        )

    failing_regimes_repaired = sum([
        1
        if risk_off_repair
        >
        0
        else 0,

        1
        if high_vol_repair
        >
        0
        else 0
    ])

    if (
        failing_regimes_repaired
        ==
        2
        and
        defensive_alpha
        >
        0
    ):
        shadow_verdict = (
            "CONTINUE_EXISTING_SHADOW_STRONGLY"
        )

    elif failing_regimes_repaired >= 1:
        shadow_verdict = (
            "CONTINUE_EXISTING_SHADOW"
        )

    else:
        shadow_verdict = (
            "NO_REGIME_REPAIR_EVIDENCE"
        )

    candidate_policy = (
        calibration_result.get(
            "shadow_candidate_policy"
        )
    )

    result = {
        "engine":
        ENGINE_VERSION,

        "attribution_signature":
        ATTRIBUTION_SIGNATURE,

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

        "source_backtest_signature":
        backtest_signature,

        "source_calibration_signature":
        calibration_signature,

        "source_robustness_verdict":
        (
            (
                walk_forward_result.get(
                    "oos_statistical_robustness",
                    {}
                )
                or
                {}
            ).get(
                "verdict"
            )
        ),

        "current_shadow_candidate":
        candidate_policy,

        "historical_oos_policy_selection_mode":
        "FOLD_BY_FOLD_PRIOR_DATA_SELECTION",

        "live_policy":
        "DEFAULT_V7_9",

        "live_policy_changed":
        False,

        "live_execution_authorized":
        False,

        "automatic_promotion_allowed":
        False,

        "primary_failure_mode":
        primary_failure_mode,

        "shadow_verdict":
        shadow_verdict,

        "failing_regimes_repaired":
        failing_regimes_repaired,

        "failing_regimes_total":
        2,

        "overall_shadow_vs_default":
        summarize_pair(
            pair[
                "default"
            ],
            pair[
                "shadow"
            ]
        ),

        "regime_repair":
        regime_results,

        "fold_diagnostics":
        fold_diagnostics,

        "divergence_attribution": {
            "forward_horizon_sessions":
            FORWARD_EVALUATION_SESSIONS,

            "minimum_exposure_divergence":
            MIN_DIVERGENCE,

            "overall":
            event_summary,

            "by_default_action":
            by_default_action,

            "event_count":
            len(
                divergence_events
            ),

            "evaluated_event_count":
            sum(
                1
                for item in divergence_events
                if item.get(
                    "evaluated"
                )
                is True
            )
        },

        "diagnostic_interpretation": {
            "risk_off_shadow_return_repair_pct_points":
            round(
                risk_off_repair,
                2
            ),

            "high_vol_shadow_return_repair_pct_points":
            round(
                high_vol_repair,
                2
            ),

            "default_reduce_exit_more_exposure_avg_shadow_alpha_20d_pct":
            round(
                defensive_alpha,
                3
            ),

            "risk_off_defensive_avg_shadow_alpha_20d_pct":
            round(
                risk_off_defensive_alpha,
                3
            ),

            "high_vol_defensive_avg_shadow_alpha_20d_pct":
            round(
                high_vol_defensive_alpha,
                3
            )
        },

        "next_gate":
        (
            "Keep MOMENTUM_FRIENDLY / historically selected policy behavior "
            "in shadow only. Require fresh 20D/60D shadow journal evidence "
            "before any live threshold review."
        ),

        "methodology": {
            "new_threshold_search":
            False,

            "policy_source":
            (
                "Existing V8.1 predeclared policy family; historical OOS folds "
                "reuse only the policy selected from prior training data."
            ),

            "regime_classification":
            (
                "Same past-only V8.4.5 SPY rules: prior 63-session trend and "
                "prior 21-session vs 126-session volatility."
            ),

            "action_attribution":
            (
                "At weekly simulated execution dates, compare default and "
                "historically selected shadow exposure. Evaluate divergence "
                "after 20 trading sessions versus SPY."
            )
        },

        "limitations": [
            (
                "Current portfolio universe still creates survivorship and "
                "selection bias."
            ),
            (
                "The policy family was designed before this diagnostic but "
                "was still evaluated on the same reconstructed history."
            ),
            (
                "Twenty-session event attribution is retrospective and must "
                "not be used as a direct live trading trigger."
            ),
            (
                "Historical news, fundamentals, events and broker execution "
                "states are not fully reconstructed."
            )
        ]
    }

    save_result(
        result
    )

    return result
