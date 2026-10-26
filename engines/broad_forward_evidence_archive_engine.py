"""
AURORA Broad Forward Evidence Archive

Forward-only archive for the current S&P 500 + Nasdaq-100 union, plus any
AURORA core scanner / portfolio names outside those indices.

Stored daily:
- headline metadata (deduplicated globally; no article body or summary)
- per-ticker news score and catalyst score/signal
- latest adjusted price / volume snapshot

Heavy Yahoo fundamental snapshots remain in the smaller V8.7 core archive.
SEC EDGAR / XBRL is the preferred fundamental evidence source for the broad
universe.

This engine does not change live decisions or authorize broker execution.
"""

from datetime import datetime, timezone
import csv
import hashlib
import json
import os

import pandas as pd
import yfinance as yf

from engines.evidence_archive_engine import (
    fetch_news_records
)

from engines.news_engine import (
    analyze_news
)

from engines.catalyst_engine import (
    analyze_catalyst
)


ENGINE_VERSION = "V8.8.2 Broad Forward Evidence Archive"
SIGNATURE = "V8.8.2"

CURRENT_INDEX_UNIVERSE_FILE = "data/current_index_universe/latest.json"
CORE_UNIVERSE_FILE = "data/us_universe.json"
PORTFOLIO_FILE = "data/portfolio.csv"

ARCHIVE_DIR = "data/broad_evidence_archive"

NEWS_COUNT = 5
PRICE_BATCH_SIZE = 100


def normalize_ticker(
    value
):
    return (
        str(
            value
            or
            ""
        )
        .strip()
        .upper()
        .replace(
            ".",
            "-"
        )
    )


def load_core_tickers():
    tickers = set()

    try:
        with open(
            CORE_UNIVERSE_FILE,
            "r",
            encoding="utf-8"
        ) as file:
            data = json.load(
                file
            )

        if isinstance(
            data,
            list
        ):
            for item in data:
                ticker = normalize_ticker(
                    (
                        item
                        or
                        {}
                    ).get(
                        "ticker"
                    )
                )

                if ticker:
                    tickers.add(
                        ticker
                    )

    except Exception:
        pass

    try:
        with open(
            PORTFOLIO_FILE,
            "r",
            encoding="utf-8"
        ) as file:
            reader = csv.DictReader(
                file
            )

            for row in reader:
                ticker = normalize_ticker(
                    row.get(
                        "ticker"
                    )
                )

                if ticker:
                    tickers.add(
                        ticker
                    )

    except Exception:
        pass

    return tickers


def load_broad_universe():
    index_tickers = set()
    snapshot_date = None
    source = "CORE_ONLY_FALLBACK"

    try:
        with open(
            CURRENT_INDEX_UNIVERSE_FILE,
            "r",
            encoding="utf-8"
        ) as file:
            data = json.load(
                file
            )

        for item in (
            data.get(
                "union",
                []
            )
            or
            []
        ):
            ticker = normalize_ticker(
                item
            )

            if ticker:
                index_tickers.add(
                    ticker
                )

        if index_tickers:
            source = "CURRENT_SP500_NASDAQ100_UNION"

            snapshot_date = data.get(
                "snapshot_date_utc"
            )

    except Exception:
        pass

    core_tickers = load_core_tickers()

    union = sorted(
        index_tickers
        |
        core_tickers
    )

    return {
        "tickers":
        union,

        "index_tickers":
        sorted(
            index_tickers
        ),

        "core_tickers":
        sorted(
            core_tickers
        ),

        "source":
        source,

        "index_snapshot_date":
        snapshot_date
    }


def _extract_batch_series(
    data,
    ticker,
    field,
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
                    field
                ]

            elif ticker in level_one:
                series = data.xs(
                    ticker,
                    axis=1,
                    level=1
                )[
                    field
                ]

            else:
                return None

        else:
            if (
                batch_count
                !=
                1
                or
                field
                not in data.columns
            ):
                return None

            series = data[
                field
            ]

        series = series.dropna()

        return (
            series
            if not series.empty
            else None
        )

    except Exception:
        return None


def fetch_price_snapshots(
    tickers
):
    snapshots = {}

    for start in range(
        0,
        len(
            tickers
        ),
        PRICE_BATCH_SIZE
    ):
        batch = tickers[
            start:
            start
            +
            PRICE_BATCH_SIZE
        ]

        try:
            data = yf.download(
                tickers=batch,
                period="5d",
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
            close = _extract_batch_series(
                data,
                ticker,
                "Close",
                len(
                    batch
                )
            )

            volume = _extract_batch_series(
                data,
                ticker,
                "Volume",
                len(
                    batch
                )
            )

            if close is None:
                continue

            last_date = close.index[
                -1
            ]

            last_close = float(
                close.iloc[
                    -1
                ]
            )

            last_volume = (
                int(
                    volume.iloc[
                        -1
                    ]
                )
                if volume is not None
                else None
            )

            snapshots[
                ticker
            ] = {
                "market_date":
                str(
                    pd.Timestamp(
                        last_date
                    ).date()
                ),

                "adjusted_close":
                round(
                    last_close,
                    6
                ),

                "volume":
                last_volume,

                "data_quality":
                "LIVE"
            }

    return snapshots


def article_key(
    article
):
    raw = (
        str(
            article.get(
                "url"
            )
            or
            ""
        )
        +
        "|"
        +
        str(
            article.get(
                "headline"
            )
            or
            ""
        )
        +
        "|"
        +
        str(
            article.get(
                "published_at"
            )
            or
            ""
        )
    )

    return hashlib.sha256(
        raw.encode(
            "utf-8"
        )
    ).hexdigest()[
        :20
    ]


def archive_news_for_ticker(
    ticker
):
    errors = []

    try:
        (
            records,
            scoring_text
        ) = fetch_news_records(
            ticker,
            count=NEWS_COUNT
        )

    except Exception as error:
        records = []
        scoring_text = []

        errors.append(
            "NEWS_FETCH:"
            +
            str(
                error
            )
        )

    try:
        news_result = analyze_news(
            ticker,
            news_items=scoring_text
        )

    except Exception as error:
        news_result = {
            "ticker":
            ticker,

            "news_score":
            None,

            "events":
            [],

            "article_count":
            len(
                scoring_text
            ),

            "data_quality":
            "ERROR"
        }

        errors.append(
            "NEWS_SCORE:"
            +
            str(
                error
            )
        )

    try:
        catalyst_result = analyze_catalyst(
            ticker,
            news_items=scoring_text
        )

    except Exception as error:
        catalyst_result = {
            "ticker":
            ticker,

            "catalyst_score":
            None,

            "catalyst_signal":
            None,

            "catalysts":
            [],

            "article_count":
            len(
                scoring_text
            ),

            "data_quality":
            "ERROR"
        }

        errors.append(
            "CATALYST:"
            +
            str(
                error
            )
        )

    return {
        "articles":
        records,

        "news_result":
        news_result,

        "catalyst_result":
        catalyst_result,

        "errors":
        errors
    }


def run_broad_forward_evidence_archive():
    now = datetime.now(
        timezone.utc
    )

    archive_date = now.date().isoformat()
    retrieval_time = now.isoformat()

    universe = load_broad_universe()

    tickers = universe[
        "tickers"
    ]

    prices = fetch_price_snapshots(
        tickers
    )

    articles = {}
    ticker_records = []
    news_live_count = 0
    error_tickers = []

    for ticker in tickers:
        news_bundle = archive_news_for_ticker(
            ticker
        )

        article_keys = []

        for article in news_bundle[
            "articles"
        ]:
            key = article_key(
                article
            )

            article_keys.append(
                key
            )

            if key not in articles:
                articles[
                    key
                ] = {
                    "article_id":
                    key,

                    "headline":
                    article.get(
                        "headline"
                    ),

                    "source":
                    article.get(
                        "source"
                    ),

                    "url":
                    article.get(
                        "url"
                    ),

                    "published_at":
                    article.get(
                        "published_at"
                    ),

                    "related_tickers":
                    article.get(
                        "related_tickers",
                        []
                    ),

                    "matched_tickers":
                    []
                }

            if ticker not in articles[
                key
            ][
                "matched_tickers"
            ]:
                articles[
                    key
                ][
                    "matched_tickers"
                ].append(
                    ticker
                )

        news_result = (
            news_bundle.get(
                "news_result",
                {}
            )
            or
            {}
        )

        catalyst_result = (
            news_bundle.get(
                "catalyst_result",
                {}
            )
            or
            {}
        )

        if (
            news_result.get(
                "data_quality"
            )
            ==
            "LIVE"
        ):
            news_live_count += 1

        if news_bundle[
            "errors"
        ]:
            error_tickers.append(
                ticker
            )

        ticker_records.append({
            "ticker":
            ticker,

            "retrieved_at":
            retrieval_time,

            "price_snapshot":
            prices.get(
                ticker,
                {
                    "data_quality":
                    "MISSING"
                }
            ),

            "article_ids":
            article_keys,

            "news_score":
            news_result.get(
                "news_score"
            ),

            "news_events":
            news_result.get(
                "events",
                []
            ),

            "news_data_quality":
            news_result.get(
                "data_quality"
            ),

            "catalyst_score":
            catalyst_result.get(
                "catalyst_score"
            ),

            "catalyst_signal":
            catalyst_result.get(
                "catalyst_signal"
            ),

            "catalysts":
            catalyst_result.get(
                "catalysts",
                []
            ),

            "catalyst_data_quality":
            catalyst_result.get(
                "data_quality"
            ),

            "errors":
            news_bundle[
                "errors"
            ]
        })

    article_rows = sorted(
        articles.values(),
        key=lambda item: (
            str(
                item.get(
                    "published_at"
                    or
                    ""
                )
            ),
            str(
                item.get(
                    "article_id"
                    or
                    ""
                )
            )
        )
    )

    for article in article_rows:
        article[
            "matched_tickers"
        ] = sorted(
            article[
                "matched_tickers"
            ]
        )

    result = {
        "engine":
        ENGINE_VERSION,

        "signature":
        SIGNATURE,

        "archive_date":
        archive_date,

        "retrieved_at":
        retrieval_time,

        "status":
        "COMPLETE",

        "point_in_time_forward_archive":
        True,

        "universe": {
            "source":
            universe[
                "source"
            ],

            "index_snapshot_date":
            universe[
                "index_snapshot_date"
            ],

            "index_union_count":
            len(
                universe[
                    "index_tickers"
                ]
            ),

            "core_count":
            len(
                universe[
                    "core_tickers"
                ]
            ),

            "archived_ticker_count":
            len(
                tickers
            )
        },

        "coverage": {
            "price_live_tickers":
            len(
                prices
            ),

            "news_live_tickers":
            news_live_count,

            "unique_articles":
            len(
                article_rows
            ),

            "error_ticker_count":
            len(
                error_tickers
            ),

            "error_tickers":
            error_tickers
        },

        "archive_policy": {
            "news_count_requested_per_ticker":
            NEWS_COUNT,

            "article_body_stored":
            False,

            "article_summary_stored":
            False,

            "headline_metadata_stored":
            True,

            "articles_deduplicated_globally":
            True,

            "price_snapshot_stored":
            True,

            "heavy_yahoo_fundamentals_stored":
            False,

            "fundamental_source":
            "SEC_EDGAR_PIT_FOUNDATION"
        },

        "articles":
        article_rows,

        "ticker_records":
        ticker_records,

        "live_decisions_changed":
        False,

        "paper_order_submission_authorized":
        False,

        "live_execution_authorized":
        False
    }

    os.makedirs(
        ARCHIVE_DIR,
        exist_ok=True
    )

    daily_file = os.path.join(
        ARCHIVE_DIR,
        archive_date
        +
        ".json"
    )

    summary_file = os.path.join(
        ARCHIVE_DIR,
        "latest_summary.json"
    )

    with open(
        daily_file,
        "w",
        encoding="utf-8"
    ) as file:
        json.dump(
            result,
            file,
            indent=2,
            ensure_ascii=False
        )

    summary = {
        "engine":
        ENGINE_VERSION,

        "signature":
        SIGNATURE,

        "archive_date":
        archive_date,

        "retrieved_at":
        retrieval_time,

        "status":
        "COMPLETE",

        "archive_file":
        daily_file,

        "universe":
        result[
            "universe"
        ],

        "coverage":
        result[
            "coverage"
        ],

        "live_decisions_changed":
        False,

        "paper_order_submission_authorized":
        False,

        "live_execution_authorized":
        False
    }

    with open(
        summary_file,
        "w",
        encoding="utf-8"
    ) as file:
        json.dump(
            summary,
            file,
            indent=2,
            ensure_ascii=False
        )

    return (
        result,
        daily_file,
        summary_file
    )
