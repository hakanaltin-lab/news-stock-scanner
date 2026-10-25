"""
V8.4 AURORA Historical Evidence Recovery Engine

Purpose:
- Recover historical scanner evidence from Git history without pretending
  different model generations used the same signal language.
- Use one end-of-day snapshot per calendar date to avoid 30-minute report
  commits overweighting the sample.
- Recover three distinct cohorts:
    1) LEGACY_OPPORTUNITY: old CSV top-ranked opportunity observations
    2) LEGACY_PORTFOLIO_ALERT: explicit old dashboard portfolio labels
    3) MODERN_ACTION: BUY / ADD / ACCUMULATE / REDUCE / EXIT from JSON
- Exclude non-LIVE / FOUNDATION modern snapshots.
- Measure 5 / 20 / 60 trading-session outcomes versus SPY.
- Report action-level evidence, especially REDUCE and EXIT separately.

Important:
- Legacy opportunity scores are NOT relabeled as BUY signals.
- Legacy RISK / ALARM and DİKKAT are kept as legacy defensive alerts,
  not relabeled as REDUCE or EXIT.
- Historical evidence is observational validation, not a full portfolio backtest.
- No broker orders are sent.
"""

from datetime import datetime, timezone
import csv
import hashlib
import html
import io
import json
import os
import re
import subprocess

from engines.recommendation_performance_engine import (
    extract_snapshot_signals,
    get_close_frame,
    parse_date,
    price_on_or_before,
    safe_float
)


ENGINE_VERSION = (
    "V8.4 Historical Evidence Recovery Engine"
)

RECOVERY_SIGNATURE = "V8.4.1"

OUTPUT_FILE = (
    "docs/historical_evidence_recovery.json"
)

HORIZONS = {
    "5d": 5,
    "20d": 20,
    "60d": 60
}

LEGACY_OPPORTUNITY_MIN_SCORE = 75.0

LEGACY_OPPORTUNITY_MAX_RANK = 10

LEGACY_DEFENSIVE_LABELS = {
    "RİSK / ALARM",
    "RISK / ALARM",
    "DİKKAT",
    "DIKKAT"
}

LEGACY_POSITIVE_LABELS = {
    "GÜÇLÜ / TUT",
    "GUCLU / TUT",
    "GÜÇLÜ",
    "GUCLU",
    "EKLE"
}

LEGACY_NEUTRAL_LABELS = {
    "TUT / İZLE",
    "TUT / IZLE",
    "NÖTR",
    "NOTR",
    "VERİ YOK",
    "VERI YOK"
}


def run_git(
    args,
    timeout=60
):
    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout
        )

        if result.returncode != 0:
            return None

        return result.stdout

    except Exception:
        return None


def git_commit_rows_for_path(
    path
):
    output = run_git([
        "git",
        "log",
        "--format=%H|%cI",
        "--",
        path
    ])

    if not output:
        return []

    rows = []

    for line in output.splitlines():
        if "|" not in line:
            continue

        commit_hash, commit_time = (
            line.split(
                "|",
                1
            )
        )

        commit_date = parse_date(
            commit_time
        )

        if commit_date is None:
            continue

        rows.append({
            "commit":
            commit_hash.strip(),

            "commit_time":
            commit_time.strip(),

            "date":
            commit_date
        })

    return rows


def end_of_day_commits(
    path
):
    rows = git_commit_rows_for_path(
        path
    )

    by_date = {}

    for row in rows:
        key = row[
            "date"
        ].isoformat()

        current = by_date.get(
            key
        )

        if (
            current is None
            or
            row[
                "commit_time"
            ]
            >
            current[
                "commit_time"
            ]
        ):
            by_date[
                key
            ] = row

    return [
        by_date[key]
        for key in sorted(
            by_date
        )
    ]


def git_show(
    commit_hash,
    path
):
    return run_git([
        "git",
        "show",
        (
            f"{commit_hash}:"
            f"{path}"
        )
    ])


def record_id(
    cohort,
    signal_date,
    ticker,
    action,
    origin_commit
):
    raw = "|".join([
        str(
            cohort
        ),
        str(
            signal_date
        ),
        str(
            ticker
        ),
        str(
            action
        ),
        str(
            origin_commit
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

            "excess_return_pct":
            None,

            "decision_alpha_pct":
            None,

            "benchmark_hit":
            None
        }
        for name, sessions in (
            HORIZONS.items()
        )
    }


def direction_for_action(
    action
):
    if action in {
        "ADD",
        "BUY",
        "ACCUMULATE",
        "LEGACY_OPPORTUNITY",
        "LEGACY_POSITIVE"
    }:
        return "LONG"

    if action in {
        "REDUCE",
        "EXIT",
        "LEGACY_DEFENSIVE_ALERT"
    }:
        return "DEFENSIVE"

    return "NEUTRAL"


def build_evidence_record(
    cohort,
    signal_date,
    ticker,
    action,
    signal_price,
    origin_commit,
    model_version=None,
    legacy_label=None,
    score=None,
    rank=None,
    source=None
):
    return {
        "id":
        record_id(
            cohort,
            signal_date,
            ticker,
            action,
            origin_commit
        ),

        "cohort":
        cohort,

        "signal_date":
        signal_date,

        "ticker":
        ticker,

        "action":
        action,

        "direction":
        direction_for_action(
            action
        ),

        "signal_price_snapshot":
        (
            round(
                safe_float(
                    signal_price
                ),
                4
            )
            if safe_float(
                signal_price
            )
            >
            0
            else None
        ),

        "origin_commit":
        origin_commit,

        "model_version":
        model_version,

        "legacy_label":
        legacy_label,

        "score":
        (
            round(
                safe_float(
                    score
                ),
                2
            )
            if score is not None
            else None
        ),

        "rank":
        rank,

        "source":
        source,

        "evaluation_basis":
        "yfinance_adjusted_close_on_signal_date_to_future_close",

        "horizons":
        blank_horizons()
    }


def recover_legacy_opportunity_records():
    commits = end_of_day_commits(
        "docs/latest.csv"
    )

    records = []

    prior_members = set()

    scanned_dates = 0

    usable_dates = 0

    for row in commits:
        raw = git_show(
            row[
                "commit"
            ],
            "docs/latest.csv"
        )

        if not raw:
            continue

        scanned_dates += 1

        try:
            reader = csv.DictReader(
                io.StringIO(
                    raw
                )
            )

            csv_rows = list(
                reader
            )

        except Exception:
            continue

        if not csv_rows:
            continue

        required = {
            "ticker",
            "price",
            "score"
        }

        if not required.issubset(
            set(
                csv_rows[0].keys()
            )
        ):
            continue

        usable_dates += 1

        selected = []

        for rank, item in enumerate(
            csv_rows,
            start=1
        ):
            if rank > LEGACY_OPPORTUNITY_MAX_RANK:
                break

            ticker = str(
                item.get(
                    "ticker",
                    ""
                )
            ).strip().upper()

            score = safe_float(
                item.get(
                    "score"
                ),
                None
            )

            price = safe_float(
                item.get(
                    "price"
                ),
                None
            )

            if (
                not ticker
                or
                score is None
                or
                score
                <
                LEGACY_OPPORTUNITY_MIN_SCORE
                or
                price is None
                or
                price
                <=
                0
            ):
                continue

            selected.append(
                ticker
            )

            if ticker in prior_members:
                continue

            records.append(
                build_evidence_record(
                    cohort=(
                        "LEGACY_OPPORTUNITY_TOP10_GE75"
                    ),
                    signal_date=row[
                        "date"
                    ].isoformat(),
                    ticker=ticker,
                    action=(
                        "LEGACY_OPPORTUNITY"
                    ),
                    signal_price=price,
                    origin_commit=row[
                        "commit"
                    ],
                    model_version=(
                        "LEGACY_CSV"
                    ),
                    score=score,
                    rank=rank,
                    source=(
                        "docs/latest.csv"
                    )
                )
            )

        prior_members = set(
            selected
        )

    return {
        "records":
        records,

        "scanned_dates":
        scanned_dates,

        "usable_dates":
        usable_dates
    }


def strip_tags(
    value
):
    text = re.sub(
        r"<[^>]+>",
        " ",
        value
    )

    text = html.unescape(
        text
    )

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()


def parse_legacy_portfolio_rows(
    raw_html
):
    start_match = re.search(
        (
            r"My Portfolio Impact"
            r".*?<table[^>]*>"
        ),
        raw_html,
        flags=(
            re.IGNORECASE
            |
            re.DOTALL
        )
    )

    if not start_match:
        return []

    remainder = raw_html[
        start_match.end():
    ]

    end_position = remainder.find(
        "</table>"
    )

    if end_position < 0:
        return []

    table_html = remainder[
        :end_position
    ]

    parsed = []

    for row_html in re.findall(
        r"<tr[^>]*>(.*?)</tr>",
        table_html,
        flags=(
            re.IGNORECASE
            |
            re.DOTALL
        )
    ):
        cells = re.findall(
            r"<td[^>]*>(.*?)</td>",
            row_html,
            flags=(
                re.IGNORECASE
                |
                re.DOTALL
            )
        )

        if len(
            cells
        ) < 5:
            continue

        ticker_match = re.search(
            r"<b>\s*([A-Z0-9.\-]+)\s*</b>",
            cells[0],
            flags=re.IGNORECASE
        )

        if not ticker_match:
            continue

        ticker = (
            ticker_match.group(
                1
            )
            .strip()
            .upper()
        )

        price = safe_float(
            strip_tags(
                cells[3]
            ).replace(
                ",",
                ""
            ),
            None
        )

        action_cell = (
            cells[-2]
            if len(
                cells
            )
            >=
            2
            else
            ""
        )

        action_match = re.search(
            r"<b>\s*(.*?)\s*</b>",
            action_cell,
            flags=(
                re.IGNORECASE
                |
                re.DOTALL
            )
        )

        if not action_match:
            continue

        label = strip_tags(
            action_match.group(
                1
            )
        ).upper()

        if label in LEGACY_DEFENSIVE_LABELS:
            action = (
                "LEGACY_DEFENSIVE_ALERT"
            )

        elif label in LEGACY_POSITIVE_LABELS:
            action = (
                "LEGACY_POSITIVE"
            )

        elif label in LEGACY_NEUTRAL_LABELS:
            action = (
                "LEGACY_NEUTRAL"
            )

        else:
            action = (
                "LEGACY_OTHER"
            )

        parsed.append({
            "ticker":
            ticker,

            "price":
            price,

            "label":
            label,

            "action":
            action
        })

    return parsed


def recover_legacy_portfolio_records():
    commits = end_of_day_commits(
        "docs/index.html"
    )

    records = []

    previous_action_by_ticker = {}

    scanned_dates = 0

    usable_dates = 0

    for row in commits:
        raw = git_show(
            row[
                "commit"
            ],
            "docs/index.html"
        )

        if not raw:
            continue

        scanned_dates += 1

        parsed = (
            parse_legacy_portfolio_rows(
                raw
            )
        )

        if not parsed:
            continue

        usable_dates += 1

        current_actions = {}

        for item in parsed:
            ticker = item[
                "ticker"
            ]

            action = item[
                "action"
            ]

            current_actions[
                ticker
            ] = action

            if action not in {
                "LEGACY_DEFENSIVE_ALERT",
                "LEGACY_POSITIVE"
            }:
                continue

            if (
                previous_action_by_ticker.get(
                    ticker
                )
                ==
                action
            ):
                continue

            records.append(
                build_evidence_record(
                    cohort=(
                        "LEGACY_PORTFOLIO_ALERT"
                    ),
                    signal_date=row[
                        "date"
                    ].isoformat(),
                    ticker=ticker,
                    action=action,
                    signal_price=item.get(
                        "price"
                    ),
                    origin_commit=row[
                        "commit"
                    ],
                    model_version=(
                        "LEGACY_HTML"
                    ),
                    legacy_label=item.get(
                        "label"
                    ),
                    source=(
                        "docs/index.html"
                    )
                )
            )

        previous_action_by_ticker.update(
            current_actions
        )

    return {
        "records":
        records,

        "scanned_dates":
        scanned_dates,

        "usable_dates":
        usable_dates
    }


def recover_modern_action_records():
    commits = end_of_day_commits(
        "docs/latest.json"
    )

    records = []

    previous_action_by_ticker = {}

    scanned_dates = 0

    usable_dates = 0

    excluded_foundation_snapshots = 0

    for row in commits:
        raw = git_show(
            row[
                "commit"
            ],
            "docs/latest.json"
        )

        if not raw:
            continue

        scanned_dates += 1

        try:
            snapshot = json.loads(
                raw
            )
        except Exception:
            continue

        extracted = (
            extract_snapshot_signals(
                snapshot,
                origin_commit=row[
                    "commit"
                ]
            )
        )

        if not extracted:
            portfolio = (
                snapshot.get(
                    "portfolio",
                    []
                )
                or
                []
            )

            if portfolio:
                qualities = [
                    (
                        (
                            item.get(
                                "market",
                                {}
                            )
                            or
                            {}
                        ).get(
                            "data_quality"
                        )
                    )
                    for item in portfolio
                ]

                if (
                    "FOUNDATION"
                    in qualities
                ):
                    excluded_foundation_snapshots += 1

            continue

        usable_dates += 1

        for item in extracted:
            ticker = item.get(
                "ticker"
            )

            action = item.get(
                "action"
            )

            source = item.get(
                "source"
            )

            if (
                not ticker
                or
                not action
            ):
                continue

            state_key = (
                f"{source}:"
                f"{ticker}"
            )

            if (
                previous_action_by_ticker.get(
                    state_key
                )
                ==
                action
            ):
                continue

            previous_action_by_ticker[
                state_key
            ] = action

            records.append(
                build_evidence_record(
                    cohort=(
                        "MODERN_ACTION_CHANGE"
                    ),
                    signal_date=item.get(
                        "signal_date"
                    ),
                    ticker=ticker,
                    action=action,
                    signal_price=item.get(
                        "signal_price"
                    ),
                    origin_commit=row[
                        "commit"
                    ],
                    model_version=item.get(
                        "model_version"
                    ),
                    score=(
                        (
                            item.get(
                                "scores",
                                {}
                            )
                            or
                            {}
                        ).get(
                            "alpha_score"
                        )
                    ),
                    source=source
                )
            )

    return {
        "records":
        records,

        "scanned_dates":
        scanned_dates,

        "usable_dates":
        usable_dates,

        "excluded_foundation_snapshots":
        excluded_foundation_snapshots
    }


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

    direction = record.get(
        "direction"
    )

    if (
        signal_date is None
        or
        not ticker
        or
        ticker not in close_frame.columns
        or
        "SPY" not in close_frame.columns
    ):
        return record

    if direction not in {
        "LONG",
        "DEFENSIVE"
    }:
        return record

    stock = close_frame[
        ticker
    ].dropna()

    spy = close_frame[
        "SPY"
    ].dropna()

    entry_stock = safe_float(
        price_on_or_before(
            stock,
            signal_date
        ),
        None
    )

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

    for horizon_name, sessions in (
        HORIZONS.items()
    ):
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

        decision_alpha = (
            excess
            if direction
            ==
            "LONG"
            else
            -excess
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

            "excess_return_pct":
            round(
                excess,
                2
            ),

            "decision_alpha_pct":
            round(
                decision_alpha,
                2
            ),

            "benchmark_hit":
            decision_alpha
            >
            0
        }

    return record


def aggregate(
    records,
    horizon_name
):
    evaluated = []

    pending = 0

    for record in records:
        horizon = (
            (
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
            or
            {}
        )

        if (
            horizon.get(
                "status"
            )
            ==
            "EVALUATED"
        ):
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

            "benchmark_hit_rate_pct":
            None,

            "average_decision_alpha_pct":
            None,

            "average_stock_return_pct":
            None,

            "average_spy_return_pct":
            None
        }

    hits = sum(
        1
        for item in evaluated
        if item.get(
            "benchmark_hit"
        )
        is True
    )

    def avg(
        field
    ):
        values = [
            safe_float(
                item.get(
                    field
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
            hits
            /
            len(
                evaluated
            )
            *
            100,
            1
        ),

        "average_decision_alpha_pct":
        avg(
            "decision_alpha_pct"
        ),

        "average_stock_return_pct":
        avg(
            "stock_return_pct"
        ),

        "average_spy_return_pct":
        avg(
            "spy_return_pct"
        )
    }


def summarize_group(
    records
):
    return {
        name:
        aggregate(
            records,
            name
        )
        for name in HORIZONS
    }


def group_summary(
    records,
    dimension
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
        summarize_group(
            group
        )
        for key, group in sorted(
            groups.items()
        )
    }


def evaluate_all(
    records
):
    tickers = [
        item.get(
            "ticker"
        )
        for item in records
        if item.get(
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

    if close_frame.empty:
        return records

    return [
        evaluate_record(
            item,
            close_frame
        )
        for item in records
    ]


def run_historical_evidence_recovery():
    legacy_opportunity = (
        recover_legacy_opportunity_records()
    )

    legacy_portfolio = (
        recover_legacy_portfolio_records()
    )

    modern = (
        recover_modern_action_records()
    )

    records = (
        legacy_opportunity[
            "records"
        ]
        +
        legacy_portfolio[
            "records"
        ]
        +
        modern[
            "records"
        ]
    )

    records = evaluate_all(
        records
    )

    records.sort(
        key=lambda item: (
            item.get(
                "signal_date",
                ""
            ),
            item.get(
                "cohort",
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

    directional_records = [
        item
        for item in records
        if item.get(
            "direction"
        )
        in {
            "LONG",
            "DEFENSIVE"
        }
    ]

    modern_records = [
        item
        for item in directional_records
        if item.get(
            "cohort"
        )
        ==
        "MODERN_ACTION_CHANGE"
    ]

    defensive_modern = [
        item
        for item in modern_records
        if item.get(
            "action"
        )
        in {
            "REDUCE",
            "EXIT"
        }
    ]

    long_modern = [
        item
        for item in modern_records
        if item.get(
            "action"
        )
        in {
            "ADD",
            "BUY",
            "ACCUMULATE"
        }
    ]

    legacy_opportunity_records = [
        item
        for item in directional_records
        if item.get(
            "cohort"
        )
        ==
        "LEGACY_OPPORTUNITY_TOP10_GE75"
    ]

    legacy_defensive_records = [
        item
        for item in directional_records
        if (
            item.get(
                "cohort"
            )
            ==
            "LEGACY_PORTFOLIO_ALERT"
            and
            item.get(
                "action"
            )
            ==
            "LEGACY_DEFENSIVE_ALERT"
        )
    ]

    result = {
        "engine":
        ENGINE_VERSION,

        "recovery_signature":
        RECOVERY_SIGNATURE,

        "generated":
        datetime.now(
            timezone.utc
        ).isoformat(),

        "status":
        "COMPLETE",

        "record_count":
        len(
            records
        ),

        "directional_record_count":
        len(
            directional_records
        ),

        "oldest_signal_date":
        (
            records[0].get(
                "signal_date"
            )
            if records
            else None
        ),

        "newest_signal_date":
        (
            records[-1].get(
                "signal_date"
            )
            if records
            else None
        ),

        "recovery_coverage": {
            "legacy_csv":
            {
                "scanned_dates":
                legacy_opportunity[
                    "scanned_dates"
                ],

                "usable_dates":
                legacy_opportunity[
                    "usable_dates"
                ],

                "records":
                len(
                    legacy_opportunity[
                        "records"
                    ]
                )
            },

            "legacy_html_portfolio":
            {
                "scanned_dates":
                legacy_portfolio[
                    "scanned_dates"
                ],

                "usable_dates":
                legacy_portfolio[
                    "usable_dates"
                ],

                "records":
                len(
                    legacy_portfolio[
                        "records"
                    ]
                )
            },

            "modern_json":
            {
                "scanned_dates":
                modern[
                    "scanned_dates"
                ],

                "usable_dates":
                modern[
                    "usable_dates"
                ],

                "records":
                len(
                    modern[
                        "records"
                    ]
                ),

                "excluded_foundation_snapshots":
                modern[
                    "excluded_foundation_snapshots"
                ]
            }
        },

        "primary_evidence": {
            "modern_action_changes":
            summarize_group(
                modern_records
            ),

            "modern_by_action":
            group_summary(
                modern_records,
                "action"
            ),

            "modern_defensive_reduce_exit":
            summarize_group(
                defensive_modern
            ),

            "modern_long_add_buy_accumulate":
            summarize_group(
                long_modern
            ),

            "legacy_opportunity_top10_ge75":
            summarize_group(
                legacy_opportunity_records
            ),

            "legacy_defensive_alerts":
            summarize_group(
                legacy_defensive_records
            )
        },

        "cohort_summary":
        group_summary(
            directional_records,
            "cohort"
        ),

        "model_version_summary":
        group_summary(
            modern_records,
            "model_version"
        ),

        "methodology": {
            "snapshot_frequency":
            (
                "One end-of-day Git snapshot per calendar date."
            ),

            "modern_signal_sampling":
            (
                "Only action changes are retained to avoid repeated daily "
                "recommendations overweighting the sample."
            ),

            "legacy_opportunity_definition":
            (
                "Entry into daily top 10 with score >= 75. This is a research "
                "cohort and is NOT relabeled as BUY."
            ),

            "legacy_defensive_definition":
            (
                "Explicit dashboard RİSK / ALARM or DİKKAT transition. "
                "This is NOT relabeled as REDUCE or EXIT."
            ),

            "benchmark":
            "SPY",

            "horizons":
            HORIZONS,

            "foundation_filter":
            (
                "Modern snapshots requiring LIVE market data; FOUNDATION "
                "snapshots are excluded."
            ),

            "entry_price_basis":
            (
                "Adjusted Yahoo Finance daily close on or before signal date."
            )
        },

        "claim_guardrails": [
            (
                "The V8.0 49.6% hit rate is not a sell-only hit rate; it mixes "
                "strategic action changes. Use modern_by_action or "
                "modern_defensive_reduce_exit for sell-specific evidence."
            ),
            (
                "Legacy opportunity and portfolio-alert cohorts use older "
                "signal semantics and must not be pooled blindly with V7/V8 "
                "BUY/REDUCE/EXIT recommendations."
            ),
            (
                "This evidence recovery does not remove survivorship bias from "
                "the V8.0 current-portfolio backtest."
            )
        ],

        "records":
        records
    }

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

    return result
