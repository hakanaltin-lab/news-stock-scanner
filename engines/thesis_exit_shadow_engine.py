"""
V8.5.2 AURORA Thesis-Aware Exit Shadow Journal

Purpose:
- Compare live price-driven REDUCE / EXIT actions with V8.5 fundamental-thesis
  shadow actions on fresh forward data.
- Record every reviewed sell decision without changing the live portfolio.
- Evaluate 5 / 20 / 60 trading-session relative value versus SPY.

Interpretation:
shadow_relative_alpha =
    (thesis shadow exposure - live exposure)
    * (stock return - SPY return)

Positive alpha means the thesis-aware exposure choice was better than the
live price-driven sell exposure.

No broker orders are sent. Live actions remain unchanged.
"""

from datetime import datetime, timezone
import hashlib
import json
import os

from engines.recommendation_performance_engine import (
    get_close_frame,
    parse_date,
    price_on_or_before,
    safe_float
)


ENGINE_VERSION = (
    "V8.5.2 Thesis-Aware Exit Shadow Journal"
)

JOURNAL_FILE = (
    "docs/thesis_exit_shadow_journal.json"
)

HORIZONS = {
    "5d": 5,
    "20d": 20,
    "60d": 60
}


def live_exposure(action):
    return {
        "REDUCE": 0.50,
        "EXIT": 0.00
    }.get(
        action,
        1.00
    )


def shadow_exposure(action):
    return {
        "HOLD": 1.00,
        "WATCH": 0.75,
        "REDUCE": 0.50,
        "EXIT": 0.00
    }.get(
        action,
        1.00
    )


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
        for name, sessions in HORIZONS.items()
    }


def record_id(
    signal_date,
    ticker,
    base_action,
    shadow_action
):
    raw = "|".join([
        str(
            signal_date
        ),
        str(
            ticker
        ),
        str(
            base_action
        ),
        str(
            shadow_action
        )
    ])

    return hashlib.sha1(
        raw.encode(
            "utf-8"
        )
    ).hexdigest()[:16]


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
                "Invalid journal"
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


def save_journal(
    data
):
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

    ticker = record.get(
        "ticker"
    )

    if (
        signal_date is None
        or
        ticker not in close_frame.columns
        or
        "SPY" not in close_frame.columns
    ):
        return record

    stock = close_frame[
        ticker
    ].dropna()

    spy = close_frame[
        "SPY"
    ].dropna()

    entry_stock = safe_float(
        record.get(
            "signal_price"
        ),
        None
    )

    if (
        entry_stock is None
        or
        entry_stock <= 0
    ):
        entry_stock = safe_float(
            price_on_or_before(
                stock,
                signal_date
            ),
            None
        )

    entry_spy = safe_float(
        record.get(
            "spy_entry_price"
        ),
        None
    )

    if (
        entry_spy is None
        or
        entry_spy <= 0
    ):
        entry_spy = safe_float(
            price_on_or_before(
                spy,
                signal_date
            ),
            None
        )

    if (
        entry_stock is None
        or
        entry_spy is None
        or
        entry_stock <= 0
        or
        entry_spy <= 0
    ):
        return record

    future_dates = [
        date_value
        for date_value in spy.index
        if date_value > signal_date
    ]

    exposure_difference = safe_float(
        record.get(
            "exposure_difference"
        ),
        0
    )

    for horizon_name, sessions in (
        HORIZONS.items()
    ):
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
            continue

        if len(
            future_dates
        ) < sessions:
            continue

        evaluation_date = future_dates[
            sessions
            -
            1
        ]

        try:
            future_stock = safe_float(
                stock.loc[
                    evaluation_date
                ],
                None
            )

            future_spy = safe_float(
                spy.loc[
                    evaluation_date
                ],
                None
            )

        except Exception:
            continue

        if (
            future_stock is None
            or
            future_spy is None
            or
            future_stock <= 0
            or
            future_spy <= 0
        ):
            continue

        stock_return = (
            future_stock
            /
            entry_stock
            -
            1
        ) * 100

        spy_return = (
            future_spy
            /
            entry_spy
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


def summarize_horizon(
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

    values = [
        safe_float(
            item.get(
                "shadow_relative_alpha_pct"
            ),
            None
        )
        for item in evaluated
    ]

    values = [
        value
        for value in values
        if value is not None
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
                    values
                )
                /
                len(
                    values
                ),
                2
            )
            if values
            else None
        )
    }


def build_thesis_exit_shadow_journal(
    portfolio_results,
    market_regime_result=None
):
    market_regime_result = (
        market_regime_result
        or
        {}
    )

    signal_date = (
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

    reviewed = []

    new_records = []

    for item in portfolio_results:
        ticker = item.get(
            "ticker"
        )

        base_action = item.get(
            "portfolio_action"
        )

        if (
            not ticker
            or
            base_action not in {
                "REDUCE",
                "EXIT"
            }
        ):
            continue

        review = (
            item.get(
                "thesis_confirmation",
                {}
            )
            or
            {}
        )

        shadow_action = (
            review.get(
                "thesis_shadow_action"
            )
            or
            base_action
        )

        review_status = (
            review.get(
                "review_status"
            )
            or
            "UNKNOWN"
        )

        thesis = (
            item.get(
                "fundamental_thesis",
                {}
            )
            or
            {}
        )

        live_weight = (
            live_exposure(
                base_action
            )
        )

        shadow_weight = (
            shadow_exposure(
                shadow_action
            )
        )

        exposure_difference = (
            shadow_weight
            -
            live_weight
        )

        market = (
            item.get(
                "market",
                {}
            )
            or
            {}
        )

        signal_price = safe_float(
            market.get(
                "last_price"
            ),
            None
        )

        row = {
            "ticker":
            ticker,

            "base_action":
            base_action,

            "thesis_shadow_action":
            shadow_action,

            "review_status":
            review_status,

            "thesis_health":
            thesis.get(
                "thesis_health"
            ),

            "fundamental_score":
            thesis.get(
                "thesis_score"
            ),

            "live_exposure":
            live_weight,

            "shadow_exposure":
            shadow_weight,

            "exposure_difference":
            round(
                exposure_difference,
                2
            ),

            "divergence":
            abs(
                exposure_difference
            )
            >=
            0.05,

            "reason":
            review.get(
                "reason"
            )
        }

        reviewed.append(
            row
        )

        if (
            signal_price is None
            or
            signal_price <= 0
            or
            abs(
                exposure_difference
            )
            <
            0.05
        ):
            continue

        new_records.append({
            "id":
            record_id(
                signal_date,
                ticker,
                base_action,
                shadow_action
            ),

            "signal_date":
            signal_date,

            "recorded_at":
            datetime.now(
                timezone.utc
            ).isoformat(),

            "ticker":
            ticker,

            "base_action":
            base_action,

            "thesis_shadow_action":
            shadow_action,

            "review_status":
            review_status,

            "thesis_health":
            thesis.get(
                "thesis_health"
            ),

            "fundamental_score":
            thesis.get(
                "thesis_score"
            ),

            "live_exposure":
            live_weight,

            "shadow_exposure":
            shadow_weight,

            "exposure_difference":
            round(
                exposure_difference,
                2
            ),

            "signal_price":
            round(
                signal_price,
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
                    spy_entry_price,
                    0
                )
                >
                0
                else None
            ),

            "horizons":
            blank_horizons()
        })

    journal = load_journal()

    records = [
        record
        for record in (
            journal.get(
                "records",
                []
            )
            or
            []
        )
        if abs(
            safe_float(
                record.get(
                    "exposure_difference"
                ),
                0
            )
        )
        >=
        0.05
    ]

    ids = set(
        record.get(
            "id"
        )
        for record in records
        if record.get(
            "id"
        )
    )

    latest_state_by_ticker = {}

    for existing in records:
        ticker = existing.get(
            "ticker"
        )

        if not ticker:
            continue

        latest_state_by_ticker[
            ticker
        ] = (
            existing.get(
                "base_action"
            ),
            existing.get(
                "thesis_shadow_action"
            ),
            existing.get(
                "review_status"
            )
        )

    added = 0

    for record in new_records:
        if record.get(
            "id"
        ) in ids:
            continue

        ticker = record.get(
            "ticker"
        )

        state = (
            record.get(
                "base_action"
            ),
            record.get(
                "thesis_shadow_action"
            ),
            record.get(
                "review_status"
            )
        )

        if (
            ticker
            and
            latest_state_by_ticker.get(
                ticker
            )
            ==
            state
        ):
            continue

        ids.add(
            record.get(
                "id"
            )
        )

        records.append(
            record
        )

        if ticker:
            latest_state_by_ticker[
                ticker
            ] = state

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
        key=lambda record: (
            record.get(
                "signal_date",
                ""
            ),
            record.get(
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
        summarize_horizon(
            records,
            name
        )
        for name in HORIZONS
    }

    divergence_rows = [
        row
        for row in reviewed
        if row.get(
            "divergence"
        )
    ]

    confirmed_count = sum(
        1
        for row in reviewed
        if row.get(
            "review_status"
        )
        in {
            "CONFIRMED",
            "CONFIRMED_PARTIAL"
        }
    )

    contradicted_count = sum(
        1
        for row in reviewed
        if row.get(
            "review_status"
        )
        ==
        "CONTRADICTED"
    )

    return {
        "engine":
        ENGINE_VERSION,

        "timestamp":
        datetime.now(
            timezone.utc
        ).isoformat(),

        "status":
        "ACTIVE_SHADOW",

        "live_actions_changed":
        False,

        "reviewed_sell_count":
        len(
            reviewed
        ),

        "confirmed_or_partial_count":
        confirmed_count,

        "contradicted_count":
        contradicted_count,

        "divergence_count":
        len(
            divergence_rows
        ),

        "divergence_tickers":
        [
            row.get(
                "ticker"
            )
            for row in divergence_rows
        ],

        "current_reviews":
        reviewed,

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
            "Thesis-aware exit logic remains shadow-only until forward 20D/60D "
            "evidence shows consistent improvement over live price-driven exits."
        )
    }
