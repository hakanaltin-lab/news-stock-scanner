"""
V8.2 AURORA Shadow Policy Monitor

Purpose:
- Run the V8.1 shadow candidate beside the live V7.9 policy
- Never change live portfolio, rebalancing or capital allocation decisions
- Record only meaningful live-vs-shadow exposure divergences
- Evaluate those divergences after 20 and 60 US trading sessions
- Measure whether the shadow exposure decision added benchmark-relative value

Interpretation:
shadow_relative_alpha =
    (shadow exposure - live exposure)
    * (stock return - SPY return)

Positive alpha means the shadow policy's different exposure choice was better.
Negative alpha means the live policy was better.

No broker orders are sent.
"""

from datetime import datetime, timezone
import hashlib
import json
import os

from engines.strategic_policy_calibration_engine import (
    POLICY_FAMILY,
    policy_action,
    policy_exposure
)

from engines.recommendation_performance_engine import (
    get_close_frame,
    parse_date,
    price_on_or_before,
    safe_float
)


ENGINE_VERSION = (
    "V8.2 Shadow Policy Monitor"
)

JOURNAL_FILE = (
    "docs/shadow_policy_journal.json"
)

HORIZONS = {
    "20d": 20,
    "60d": 60
}


def live_action_exposure(action):
    return {
        "ADD": 1.00,
        "HOLD": 1.00,
        "WATCH": 0.75,
        "REDUCE": 0.50,
        "EXIT": 0.00
    }.get(
        action,
        0.75
    )


def build_policy_state(item):
    strategic = (
        item.get(
            "strategic_market",
            {}
        )
        or
        {}
    )

    metrics = (
        strategic.get(
            "metrics",
            {}
        )
        or
        {}
    )

    return {
        "trend_score":
        strategic.get(
            "strategic_trend_score"
        ),

        "risk_score":
        strategic.get(
            "strategic_risk_score"
        ),

        "return_6m_pct":
        metrics.get(
            "return_6m_pct"
        ),

        "relative_strength_6m_pct":
        metrics.get(
            "relative_strength_6m_pct"
        ),

        "above_sma200":
        metrics.get(
            "above_sma200"
        )
    }


def record_id(
    signal_date,
    ticker,
    candidate_policy
):
    raw = "|".join([
        str(
            signal_date
        ),
        str(
            ticker
        ),
        str(
            candidate_policy
        )
    ])

    return hashlib.sha1(
        raw.encode(
            "utf-8"
        )
    ).hexdigest()[:16]


def blank_horizons():
    return {
        name: {
            "target_trading_sessions":
            sessions,

            "status":
            "PENDING",

            "evaluation_date":
            None,

            "stock_return_pct":
            None,

            "spy_return_pct":
            None,

            "stock_excess_return_pct":
            None,

            "shadow_relative_alpha_pct":
            None,

            "shadow_hit":
            None
        }
        for name, sessions in (
            HORIZONS.items()
        )
    }


def load_journal():
    if not os.path.exists(
        JOURNAL_FILE
    ):
        return {
            "engine":
            ENGINE_VERSION,

            "records":
            []
        }

    try:
        with open(
            JOURNAL_FILE,
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
                "Invalid journal structure"
            )

        if not isinstance(
            data.get(
                "records"
            ),
            list
        ):
            data[
                "records"
            ] = []

        return data

    except Exception:
        return {
            "engine":
            ENGINE_VERSION,

            "records":
            []
        }


def save_journal(data):
    os.makedirs(
        os.path.dirname(
            JOURNAL_FILE
        ),
        exist_ok=True
    )

    with open(
        JOURNAL_FILE,
        "w",
        encoding="utf-8"
    ) as file:
        json.dump(
            data,
            file,
            indent=2,
            ensure_ascii=False
        )


def evaluate_record(
    record,
    close_frame
):
    signal_date = parse_date(
        record.get(
            "signal_date"
        )
    )

    if signal_date is None:
        return record

    ticker = record.get(
        "ticker"
    )

    if (
        ticker not in close_frame.columns
        or
        "SPY" not in close_frame.columns
    ):
        return record

    stock_series = close_frame[
        ticker
    ].dropna()

    spy_series = close_frame[
        "SPY"
    ].dropna()

    entry_price = safe_float(
        record.get(
            "signal_price"
        )
    )

    spy_entry = safe_float(
        record.get(
            "spy_entry_price"
        )
    )

    if spy_entry <= 0:
        spy_entry = safe_float(
            price_on_or_before(
                spy_series,
                signal_date
            )
        )

        if spy_entry > 0:
            record[
                "spy_entry_price"
            ] = round(
                spy_entry,
                4
            )

    if (
        entry_price <= 0
        or
        spy_entry <= 0
    ):
        return record

    future_dates = [
        index
        for index in spy_series.index
        if index > signal_date
    ]

    exposure_difference = safe_float(
        record.get(
            "exposure_difference"
        )
    )

    for horizon_name, sessions in (
        HORIZONS.items()
    ):
        existing = (
            record.get(
                "horizons",
                {}
            )
            or
            {}
        ).get(
            horizon_name,
            {}
        )

        if existing.get(
            "status"
        ) == "EVALUATED":
            continue

        if len(
            future_dates
        ) < sessions:
            continue

        evaluation_date = (
            future_dates[
                sessions
                -
                1
            ]
        )

        try:
            stock_future = safe_float(
                stock_series.loc[
                    evaluation_date
                ]
            )

            spy_future = safe_float(
                spy_series.loc[
                    evaluation_date
                ]
            )

        except Exception:
            continue

        if (
            stock_future <= 0
            or
            spy_future <= 0
        ):
            continue

        stock_return = (
            stock_future
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

        shadow_alpha = (
            exposure_difference
            *
            excess
        )

        record[
            "horizons"
        ][
            horizon_name
        ] = {
            "target_trading_sessions":
            sessions,

            "status":
            "EVALUATED",

            "evaluation_date":
            evaluation_date.isoformat(),

            "stock_return_pct":
            round(
                stock_return,
                2
            ),

            "spy_return_pct":
            round(
                spy_return,
                2
            ),

            "stock_excess_return_pct":
            round(
                excess,
                2
            ),

            "shadow_relative_alpha_pct":
            round(
                shadow_alpha,
                2
            ),

            "shadow_hit":
            shadow_alpha > 0
        }

    return record


def horizon_summary(
    records,
    horizon_name
):
    evaluated = []

    pending = 0

    for record in records:
        horizon = (
            record.get(
                "horizons",
                {}
            )
            or
            {}
        ).get(
            horizon_name,
            {}
        )

        if horizon.get(
            "status"
        ) == "EVALUATED":
            evaluated.append(
                horizon
            )

        else:
            pending += 1

    if not evaluated:
        return {
            "evaluated":
            0,

            "pending":
            pending,

            "shadow_hit_rate_pct":
            None,

            "average_shadow_relative_alpha_pct":
            None
        }

    hits = sum(
        1
        for item in evaluated
        if item.get(
            "shadow_hit"
        )
        is True
    )

    alpha_values = [
        safe_float(
            item.get(
                "shadow_relative_alpha_pct"
            )
        )
        for item in evaluated
        if item.get(
            "shadow_relative_alpha_pct"
        )
        is not None
    ]

    return {
        "evaluated":
        len(
            evaluated
        ),

        "pending":
        pending,

        "shadow_hit_rate_pct":
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

        "average_shadow_relative_alpha_pct":
        (
            round(
                sum(
                    alpha_values
                )
                /
                len(
                    alpha_values
                ),
                2
            )
            if alpha_values
            else None
        )
    }


def build_shadow_policy_monitor(
    portfolio_results,
    calibration_result,
    market_regime_result=None
):
    calibration_result = (
        calibration_result
        or
        {}
    )

    verdict = (
        calibration_result.get(
            "promotion_verdict",
            {}
        )
        or
        {}
    )

    verdict_status = verdict.get(
        "status"
    )

    candidate_policy_name = (
        calibration_result.get(
            "shadow_candidate_policy"
        )
    )

    if (
        verdict_status
        not in [
            "SHADOW_CANDIDATE",
            "PROMOTE_CANDIDATE"
        ]
        or
        candidate_policy_name
        not in POLICY_FAMILY
    ):
        return {
            "engine":
            ENGINE_VERSION,

            "timestamp":
            datetime.now(
                timezone.utc
            ).isoformat(),

            "status":
            "INACTIVE",

            "reason":
            (
                "No V8.1 candidate qualified for shadow monitoring."
            ),

            "live_policy_changed":
            False,

            "candidate_policy":
            candidate_policy_name,

            "current_comparisons":
            [],

            "divergence_count":
            0,

            "journal_record_count":
            0,

            "performance": {
                name:
                {
                    "evaluated":
                    0,

                    "pending":
                    0,

                    "shadow_hit_rate_pct":
                    None,

                    "average_shadow_relative_alpha_pct":
                    None
                }
                for name in HORIZONS
            }
        }

    policy = POLICY_FAMILY[
        candidate_policy_name
    ]

    market_regime_result = (
        market_regime_result
        or
        {}
    )

    market_date = (
        market_regime_result.get(
            "market_date"
        )
        or
        datetime.now(
            timezone.utc
        ).date().isoformat()
    )

    spy_entry_price = (
        (
            market_regime_result.get(
                "metrics",
                {}
            )
            or
            {}
        ).get(
            "SPY",
            {}
        ).get(
            "last_price"
        )
    )

    comparisons = []

    new_records = []

    for item in portfolio_results:
        ticker = item.get(
            "ticker"
        )

        if not ticker:
            continue

        live_action = item.get(
            "portfolio_action",
            "WATCH"
        )

        state = build_policy_state(
            item
        )

        shadow_action = policy_action(
            state,
            policy
        )

        live_exposure = (
            live_action_exposure(
                live_action
            )
        )

        shadow_exposure = (
            policy_exposure(
                shadow_action,
                policy
            )
        )

        exposure_difference = round(
            shadow_exposure
            -
            live_exposure,
            2
        )

        current_price = safe_float(
            (
                item.get(
                    "market",
                    {}
                )
                or
                {}
            ).get(
                "last_price"
            )
        )

        comparison = {
            "ticker":
            ticker,

            "live_action":
            live_action,

            "shadow_action":
            shadow_action,

            "live_exposure":
            round(
                live_exposure,
                2
            ),

            "shadow_exposure":
            round(
                shadow_exposure,
                2
            ),

            "exposure_difference":
            exposure_difference,

            "divergence":
            abs(
                exposure_difference
            )
            >=
            0.05,

            "strategic_trend_score":
            state.get(
                "trend_score"
            ),

            "strategic_risk_score":
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
        }

        comparisons.append(
            comparison
        )

        if (
            comparison.get(
                "divergence"
            )
            and
            current_price > 0
        ):
            new_records.append({
                "id":
                record_id(
                    market_date,
                    ticker,
                    candidate_policy_name
                ),

                "signal_date":
                market_date,

                "recorded_at":
                datetime.now(
                    timezone.utc
                ).isoformat(),

                "ticker":
                ticker,

                "candidate_policy":
                candidate_policy_name,

                "live_action":
                live_action,

                "shadow_action":
                shadow_action,

                "live_exposure":
                round(
                    live_exposure,
                    2
                ),

                "shadow_exposure":
                round(
                    shadow_exposure,
                    2
                ),

                "exposure_difference":
                exposure_difference,

                "signal_price":
                round(
                    current_price,
                    4
                ),

                "spy_entry_price":
                (
                    round(
                        safe_float(
                            spy_entry_price
                        ),
                        4
                    )
                    if safe_float(
                        spy_entry_price
                    )
                    >
                    0
                    else None
                ),

                "horizons":
                blank_horizons()
            })

    journal = load_journal()

    records = (
        journal.get(
            "records",
            []
        )
        or
        []
    )

    existing_ids = set(
        item.get(
            "id"
        )
        for item in records
        if item.get(
            "id"
        )
    )

    added = 0

    for record in new_records:
        if record.get(
            "id"
        ) in existing_ids:
            continue

        existing_ids.add(
            record.get(
                "id"
            )
        )

        records.append(
            record
        )

        added += 1

    tickers = [
        record.get(
            "ticker"
        )
        for record in records
        if record.get(
            "ticker"
        )
    ]

    close_frame = get_close_frame(
        tickers
        +
        [
            "SPY"
        ]
    )

    if not close_frame.empty:
        records = [
            evaluate_record(
                record,
                close_frame
            )
            for record in records
        ]

    records.sort(
        key=lambda item: (
            item.get(
                "signal_date",
                ""
            ),
            item.get(
                "ticker",
                ""
            )
        )
    )

    journal = {
        "engine":
        ENGINE_VERSION,

        "updated_at":
        datetime.now(
            timezone.utc
        ).isoformat(),

        "candidate_policy":
        candidate_policy_name,

        "record_count":
        len(
            records
        ),

        "records":
        records
    }

    save_journal(
        journal
    )

    performance = {
        name:
        horizon_summary(
            records,
            name
        )
        for name in HORIZONS
    }

    divergences = [
        item
        for item in comparisons
        if item.get(
            "divergence"
        )
    ]

    return {
        "engine":
        ENGINE_VERSION,

        "timestamp":
        datetime.now(
            timezone.utc
        ).isoformat(),

        "status":
        "ACTIVE_SHADOW",

        "candidate_policy":
        candidate_policy_name,

        "live_policy":
        "V7.9 DEFAULT",

        "live_policy_changed":
        False,

        "market_date":
        market_date,

        "current_comparisons":
        comparisons,

        "divergence_count":
        len(
            divergences
        ),

        "divergence_tickers":
        [
            item.get(
                "ticker"
            )
            for item in divergences
        ],

        "journal_records_added":
        added,

        "journal_record_count":
        len(
            records
        ),

        "performance":
        performance,

        "promotion_rule":
        (
            "Shadow evidence must mature on fresh forward data before any "
            "live policy change is considered."
        )
    }
