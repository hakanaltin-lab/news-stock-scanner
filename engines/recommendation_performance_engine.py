"""
V7.8 AURORA Recommendation Performance Journal

Purpose:
- Persist actionable AURORA recommendations
- Bootstrap usable historical recommendations from docs/latest.json Git history
- Exclude non-live / foundation test snapshots
- Evaluate every recommendation after 5 / 20 / 60 US trading sessions
- Compare stock return with SPY
- Measure whether BUY/ADD or REDUCE/EXIT decisions added benchmark-relative value

Tracked actions:
- Portfolio: ADD, REDUCE, EXIT
- New entries: BUY, ACCUMULATE when final allocation status is ALLOCATE
  or, for older versions without capital allocation, when top_actionable is live.

Evaluation:
- LONG actions (ADD / BUY / ACCUMULATE):
    decision alpha = stock return - SPY return
- DEFENSIVE actions (REDUCE / EXIT):
    decision alpha = SPY return - stock return

A positive decision alpha means the recommendation beat the benchmark-relative
alternative in the intended direction.

Important:
- This is recommendation validation, not a full portfolio backtest.
- It does not include slippage, taxes or transaction costs.
- It does not send broker orders.
"""

from datetime import datetime, date, timedelta, timezone
import hashlib
import json
import os
import subprocess

import pandas as pd
import yfinance as yf


JOURNAL_FILE = "docs/recommendation_journal.json"
PERFORMANCE_FILE = "docs/recommendation_performance.json"

HORIZONS = {
    "5d": 5,
    "20d": 20,
    "60d": 60
}

PORTFOLIO_ACTIONS = {
    "ADD",
    "REDUCE",
    "EXIT"
}

NEW_ENTRY_ACTIONS = {
    "BUY",
    "ACCUMULATE"
}


def safe_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def parse_date(value):
    if not value:
        return None

    try:
        return datetime.fromisoformat(
            str(value).replace(
                "Z",
                "+00:00"
            )
        ).date()
    except Exception:
        try:
            return datetime.strptime(
                str(value)[:10],
                "%Y-%m-%d"
            ).date()
        except Exception:
            return None


def signal_direction(action):
    if action in {
        "ADD",
        "BUY",
        "ACCUMULATE"
    }:
        return "LONG"

    if action in {
        "REDUCE",
        "EXIT"
    }:
        return "DEFENSIVE"

    return "UNKNOWN"


def signal_key(
    signal_date,
    model_version,
    source,
    ticker,
    action
):
    raw = "|".join([
        str(signal_date),
        str(model_version),
        str(source),
        str(ticker),
        str(action)
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

            "future_price":
            None,

            "future_spy_price":
            None,

            "stock_return_pct":
            None,

            "spy_return_pct":
            None,

            "excess_return_pct":
            None,

            "decision_alpha_pct":
            None,

            "benchmark_hit":
            None,

            "absolute_hit":
            None
        }
        for name, sessions in HORIZONS.items()
    }


def load_journal():
    if not os.path.exists(
        JOURNAL_FILE
    ):
        return {
            "engine":
            "V7.8 Recommendation Performance Journal",

            "bootstrap_completed":
            False,

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
            "V7.8 Recommendation Performance Journal",

            "bootstrap_completed":
            False,

            "records":
            []
        }


def save_json(
    path,
    data
):
    os.makedirs(
        os.path.dirname(
            path
        ),
        exist_ok=True
    )

    with open(
        path,
        "w",
        encoding="utf-8"
    ) as file:
        json.dump(
            data,
            file,
            indent=2,
            ensure_ascii=False
        )


def snapshot_generated_date(
    snapshot
):
    market_date = (
        (
            snapshot.get(
                "market_regime",
                {}
            )
            or
            {}
        ).get(
            "market_date"
        )
    )

    if market_date:
        parsed = parse_date(
            market_date
        )

        if parsed:
            return parsed

    return parse_date(
        snapshot.get(
            "generated"
        )
    )


def scores_from_item(
    item
):
    scores = (
        item.get(
            "scores",
            {}
        )
        or
        {}
    )

    return {
        "alpha_score":
        scores.get(
            "alpha_score"
        ),

        "market_score":
        scores.get(
            "market_score"
        ),

        "news_score":
        scores.get(
            "news_score"
        ),

        "catalyst_score":
        scores.get(
            "catalyst_score"
        ),

        "sector_score":
        scores.get(
            "sector_score"
        ),

        "risk_score":
        scores.get(
            "risk_score"
        )
    }


def build_record(
    signal_date,
    generated_at,
    model_version,
    source,
    ticker,
    action,
    signal_price,
    benchmark_price=None,
    scores=None,
    origin_commit=None
):
    direction = signal_direction(
        action
    )

    record_id = signal_key(
        signal_date.isoformat(),
        model_version,
        source,
        ticker,
        action
    )

    return {
        "id":
        record_id,

        "signal_date":
        signal_date.isoformat(),

        "generated_at":
        generated_at,

        "model_version":
        model_version,

        "source":
        source,

        "ticker":
        ticker,

        "action":
        action,

        "direction":
        direction,

        "signal_price":
        round(
            safe_float(
                signal_price
            ),
            4
        ),

        "benchmark":
        "SPY",

        "benchmark_entry_price":
        (
            round(
                safe_float(
                    benchmark_price
                ),
                4
            )
            if safe_float(
                benchmark_price
            ) > 0
            else None
        ),

        "scores":
        scores
        or
        {},

        "origin_commit":
        origin_commit,

        "evaluation_basis":
        "signal_price_to_future_daily_close",

        "horizons":
        blank_horizons()
    }


def live_market_item(
    item
):
    market = (
        item.get(
            "market",
            {}
        )
        or
        {}
    )

    return (
        market.get(
            "data_quality"
        )
        ==
        "LIVE"
        and
        safe_float(
            market.get(
                "last_price",
                0
            )
        )
        >
        0
    )


def extract_snapshot_signals(
    snapshot,
    origin_commit=None
):
    signal_date = (
        snapshot_generated_date(
            snapshot
        )
    )

    if signal_date is None:
        return []

    generated_at = (
        snapshot.get(
            "generated"
        )
        or
        datetime.now(
            timezone.utc
        ).isoformat()
    )

    model_version = (
        snapshot.get(
            "scanner_version"
        )
        or
        "UNKNOWN"
    )

    benchmark_price = (
        (
            (
                snapshot.get(
                    "market_regime",
                    {}
                )
                or
                {}
            ).get(
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

    records = []

    # Existing portfolio recommendations.
    for item in (
        snapshot.get(
            "portfolio",
            []
        )
        or
        []
    ):
        action = item.get(
            "portfolio_action"
        )

        if action not in PORTFOLIO_ACTIONS:
            continue

        if not live_market_item(
            item
        ):
            continue

        ticker = item.get(
            "ticker"
        )

        price = (
            item.get(
                "market",
                {}
            )
            or
            {}
        ).get(
            "last_price"
        )

        if (
            not ticker
            or
            safe_float(
                price
            )
            <=
            0
        ):
            continue

        records.append(
            build_record(
                signal_date=signal_date,
                generated_at=generated_at,
                model_version=model_version,
                source="PORTFOLIO",
                ticker=ticker,
                action=action,
                signal_price=price,
                benchmark_price=benchmark_price,
                scores=scores_from_item(
                    item
                ),
                origin_commit=origin_commit
            )
        )

    # New-entry recommendations.
    capital = (
        snapshot.get(
            "capital_allocation",
            {}
        )
        or
        {}
    )

    allocation_plan = (
        capital.get(
            "allocation_plan",
            []
        )
        or
        []
    )

    if allocation_plan:
        opportunity_lookup = {
            item.get(
                "ticker"
            ):
            item
            for item in (
                (
                    snapshot.get(
                        "opportunity_analysis",
                        {}
                    )
                    or
                    {}
                ).get(
                    "top_actionable",
                    []
                )
                or
                []
            )
            if item.get(
                "ticker"
            )
        }

        for item in allocation_plan:
            action = item.get(
                "action"
            )

            if (
                action
                not in
                NEW_ENTRY_ACTIONS
                or
                item.get(
                    "allocation_status"
                )
                !=
                "ALLOCATE"
            ):
                continue

            ticker = item.get(
                "ticker"
            )

            price = item.get(
                "price"
            )

            source_item = (
                opportunity_lookup.get(
                    ticker,
                    {}
                )
                or
                {}
            )

            if (
                source_item
                and
                not live_market_item(
                    source_item
                )
            ):
                continue

            if (
                not ticker
                or
                safe_float(
                    price
                )
                <=
                0
            ):
                continue

            records.append(
                build_record(
                    signal_date=signal_date,
                    generated_at=generated_at,
                    model_version=model_version,
                    source="NEW_ENTRY",
                    ticker=ticker,
                    action=action,
                    signal_price=price,
                    benchmark_price=benchmark_price,
                    scores={
                        "alpha_score":
                        item.get(
                            "alpha_score"
                        ),

                        "risk_score":
                        item.get(
                            "risk_score"
                        ),

                        "confidence":
                        item.get(
                            "confidence"
                        )
                    },
                    origin_commit=origin_commit
                )
            )

    else:
        # Older versions before capital allocation.
        opportunity_analysis = (
            snapshot.get(
                "opportunity_analysis",
                {}
            )
            or
            {}
        )

        for item in (
            opportunity_analysis.get(
                "top_actionable",
                []
            )
            or
            []
        ):
            action = item.get(
                "action"
            )

            if action not in NEW_ENTRY_ACTIONS:
                continue

            if not live_market_item(
                item
            ):
                continue

            ticker = item.get(
                "ticker"
            )

            price = (
                item.get(
                    "market",
                    {}
                )
                or
                {}
            ).get(
                "last_price"
            )

            if (
                not ticker
                or
                safe_float(
                    price
                )
                <=
                0
            ):
                continue

            records.append(
                build_record(
                    signal_date=signal_date,
                    generated_at=generated_at,
                    model_version=model_version,
                    source="NEW_ENTRY",
                    ticker=ticker,
                    action=action,
                    signal_price=price,
                    benchmark_price=benchmark_price,
                    scores=scores_from_item(
                        item
                    ),
                    origin_commit=origin_commit
                )
            )

    return records


def run_git_command(
    args
):
    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            check=False,
            timeout=20
        )

        if result.returncode != 0:
            return None

        return result.stdout

    except Exception:
        return None


def bootstrap_from_git_history(
    existing_ids,
    max_commits=500
):
    output = run_git_command([
        "git",
        "log",
        f"-n{max_commits}",
        "--format=%H",
        "--",
        "docs/latest.json"
    ])

    if not output:
        return []

    commit_hashes = [
        line.strip()
        for line in output.splitlines()
        if line.strip()
    ]

    records = []

    # Oldest first keeps the journal naturally chronological.
    for commit_hash in reversed(
        commit_hashes
    ):
        raw = run_git_command([
            "git",
            "show",
            f"{commit_hash}:docs/latest.json"
        ])

        if not raw:
            continue

        try:
            snapshot = json.loads(
                raw
            )
        except Exception:
            continue

        for record in extract_snapshot_signals(
            snapshot,
            origin_commit=commit_hash
        ):
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

    return records


def get_close_frame(
    tickers
):
    tickers = [
        ticker
        for ticker in dict.fromkeys(
            tickers
        )
        if ticker
    ]

    if not tickers:
        return pd.DataFrame()

    try:
        data = yf.download(
            tickers=tickers,
            period="1y",
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

            clean = (
                series
                .dropna()
                .copy()
            )

            clean.index = pd.to_datetime(
                clean.index
            ).date

            close_data[
                ticker
            ] = clean

        except Exception:
            continue

    if not close_data:
        return pd.DataFrame()

    return pd.DataFrame(
        close_data
    ).sort_index()


def price_on_or_before(
    series,
    target_date
):
    if series is None:
        return None

    try:
        eligible = series[
            series.index
            <=
            target_date
        ].dropna()

        if eligible.empty:
            return None

        return safe_float(
            eligible.iloc[-1],
            None
        )

    except Exception:
        return None


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

    benchmark_entry = safe_float(
        record.get(
            "benchmark_entry_price"
        )
    )

    if benchmark_entry <= 0:
        benchmark_entry = safe_float(
            price_on_or_before(
                spy_series,
                signal_date
            )
        )

        if benchmark_entry > 0:
            record[
                "benchmark_entry_price"
            ] = round(
                benchmark_entry,
                4
            )

    if (
        entry_price <= 0
        or
        benchmark_entry <= 0
    ):
        return record

    future_spy_dates = [
        index
        for index in spy_series.index
        if index > signal_date
    ]

    direction = record.get(
        "direction"
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
            future_spy_dates
        ) < sessions:
            continue

        evaluation_date = (
            future_spy_dates[
                sessions - 1
            ]
        )

        try:
            future_spy_price = safe_float(
                spy_series.loc[
                    evaluation_date
                ]
            )
        except Exception:
            continue

        try:
            future_stock_price = safe_float(
                stock_series.loc[
                    evaluation_date
                ]
            )
        except Exception:
            continue

        if (
            future_spy_price <= 0
            or
            future_stock_price <= 0
        ):
            continue

        stock_return = (
            future_stock_price
            /
            entry_price
            -
            1
        ) * 100

        spy_return = (
            future_spy_price
            /
            benchmark_entry
            -
            1
        ) * 100

        excess_return = (
            stock_return
            -
            spy_return
        )

        if direction == "DEFENSIVE":
            decision_alpha = (
                -excess_return
            )

            absolute_result = (
                -stock_return
            )

        else:
            decision_alpha = (
                excess_return
            )

            absolute_result = (
                stock_return
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

            "future_price":
            round(
                future_stock_price,
                4
            ),

            "future_spy_price":
            round(
                future_spy_price,
                4
            ),

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

            "excess_return_pct":
            round(
                excess_return,
                2
            ),

            "decision_alpha_pct":
            round(
                decision_alpha,
                2
            ),

            "benchmark_hit":
            decision_alpha > 0,

            "absolute_hit":
            absolute_result > 0
        }

    return record


def aggregate_horizon(
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
                (
                    record,
                    horizon
                )
            )
        else:
            pending += 1

    if not evaluated:
        return {
            "evaluated":
            0,

            "pending":
            pending,

            "benchmark_hit_rate_pct":
            None,

            "absolute_hit_rate_pct":
            None,

            "average_stock_return_pct":
            None,

            "average_spy_return_pct":
            None,

            "average_excess_return_pct":
            None,

            "average_decision_alpha_pct":
            None
        }

    benchmark_hits = sum(
        1
        for _, horizon in evaluated
        if horizon.get(
            "benchmark_hit"
        )
        is True
    )

    absolute_hits = sum(
        1
        for _, horizon in evaluated
        if horizon.get(
            "absolute_hit"
        )
        is True
    )

    def average(field):
        values = [
            safe_float(
                horizon.get(
                    field
                )
            )
            for _, horizon in evaluated
            if horizon.get(
                field
            )
            is not None
        ]

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
            2
        )

    return {
        "evaluated":
        len(
            evaluated
        ),

        "pending":
        pending,

        "benchmark_hit_rate_pct":
        round(
            benchmark_hits
            /
            len(
                evaluated
            )
            *
            100,
            1
        ),

        "absolute_hit_rate_pct":
        round(
            absolute_hits
            /
            len(
                evaluated
            )
            *
            100,
            1
        ),

        "average_stock_return_pct":
        average(
            "stock_return_pct"
        ),

        "average_spy_return_pct":
        average(
            "spy_return_pct"
        ),

        "average_excess_return_pct":
        average(
            "excess_return_pct"
        ),

        "average_decision_alpha_pct":
        average(
            "decision_alpha_pct"
        )
    }


def aggregate_by_dimension(
    records,
    dimension,
    horizon_name="20d"
):
    groups = {}

    for record in records:
        key = record.get(
            dimension
        )

        if not key:
            continue

        groups.setdefault(
            key,
            []
        ).append(
            record
        )

    return {
        key:
        aggregate_horizon(
            group_records,
            horizon_name
        )
        for key, group_records in groups.items()
    }


def build_summary(
    records,
    bootstrap_added,
    new_records_added
):
    records = sorted(
        records,
        key=lambda item: (
            item.get(
                "signal_date",
                ""
            ),
            item.get(
                "ticker",
                ""
            ),
            item.get(
                "action",
                ""
            )
        )
    )

    versions = sorted(
        set(
            record.get(
                "model_version"
            )
            for record in records
            if record.get(
                "model_version"
            )
        )
    )

    oldest = (
        records[0].get(
            "signal_date"
        )
        if records
        else None
    )

    newest = (
        records[-1].get(
            "signal_date"
        )
        if records
        else None
    )

    return {
        "engine":
        "V7.8 Recommendation Performance Journal",

        "generated":
        datetime.now(
            timezone.utc
        ).isoformat(),

        "total_signals":
        len(
            records
        ),

        "bootstrap_signals_added":
        bootstrap_added,

        "new_signals_added":
        new_records_added,

        "oldest_signal_date":
        oldest,

        "newest_signal_date":
        newest,

        "model_versions":
        versions,

        "horizons": {
            name:
            aggregate_horizon(
                records,
                name
            )
            for name in HORIZONS
        },

        "by_action_20d":
        aggregate_by_dimension(
            records,
            "action",
            "20d"
        ),

        "by_model_version_20d":
        aggregate_by_dimension(
            records,
            "model_version",
            "20d"
        ),

        "methodology": {
            "long_actions":
            [
                "ADD",
                "BUY",
                "ACCUMULATE"
            ],

            "defensive_actions":
            [
                "REDUCE",
                "EXIT"
            ],

            "benchmark":
            "SPY",

            "horizons_trading_sessions":
            HORIZONS,

            "benchmark_hit_definition":
            (
                "LONG: stock outperforms SPY. "
                "DEFENSIVE: stock underperforms SPY."
            ),

            "excludes":
            [
                "transaction costs",
                "slippage",
                "taxes"
            ]
        }
    }


def update_recommendation_performance(
    current_snapshot
):
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
        record.get(
            "id"
        )
        for record in records
        if record.get(
            "id"
        )
    )

    bootstrap_added = 0

    if not journal.get(
        "bootstrap_completed"
    ):
        bootstrapped = (
            bootstrap_from_git_history(
                existing_ids
            )
        )

        records.extend(
            bootstrapped
        )

        bootstrap_added = len(
            bootstrapped
        )

        journal[
            "bootstrap_completed"
        ] = True

    current_records = (
        extract_snapshot_signals(
            current_snapshot,
            origin_commit="CURRENT_RUN"
        )
    )

    new_records_added = 0

    for record in current_records:
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

        new_records_added += 1

    tickers = [
        record.get(
            "ticker"
        )
        for record in records
        if record.get(
            "ticker"
        )
    ]

    close_frame = (
        get_close_frame(
            tickers
            +
            [
                "SPY"
            ]
        )
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
                "model_version",
                ""
            ),
            item.get(
                "source",
                ""
            ),
            item.get(
                "ticker",
                ""
            ),
            item.get(
                "action",
                ""
            )
        )
    )

    summary = build_summary(
        records,
        bootstrap_added,
        new_records_added
    )

    journal.update({
        "engine":
        "V7.8 Recommendation Performance Journal",

        "updated_at":
        datetime.now(
            timezone.utc
        ).isoformat(),

        "bootstrap_completed":
        True,

        "record_count":
        len(
            records
        ),

        "records":
        records
    })

    save_json(
        JOURNAL_FILE,
        journal
    )

    save_json(
        PERFORMANCE_FILE,
        summary
    )

    return summary
