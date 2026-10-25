"""
AURORA Daily Evidence Archive Engine

Purpose:
- Preserve forward-looking evidence from the day it becomes available.
- Archive the current live universe + portfolio union once per day.
- Store news headline metadata (not article bodies), news/catalyst scores,
  and current fundamental-thesis snapshots.
- Create future point-in-time evidence without changing live decisions.

This archive is observational only. It does not authorize broker execution.
"""

from datetime import datetime, timezone
import csv
import json
import os

import yfinance as yf

from engines.news_engine import analyze_news
from engines.catalyst_engine import analyze_catalyst
from engines.fundamental_thesis_engine import (
    analyze_fundamental_thesis
)


ENGINE_VERSION = "V8.7 Daily Forward Evidence Archive"
ARCHIVE_SIGNATURE = "V8.7.0"

UNIVERSE_FILE = "data/us_universe.json"
PORTFOLIO_FILE = "data/portfolio.csv"
ARCHIVE_DIR = "data/evidence_archive"

NEWS_COUNT = 10


def load_tickers():
    tickers = set()

    try:
        with open(
            UNIVERSE_FILE,
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
                ticker = str(
                    (
                        item
                        or
                        {}
                    ).get(
                        "ticker",
                        ""
                    )
                ).strip().upper()

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
                ticker = str(
                    row.get(
                        "ticker",
                        ""
                    )
                ).strip().upper()

                if ticker:
                    tickers.add(
                        ticker
                    )

    except Exception:
        pass

    return sorted(
        tickers
    )


def nested_value(
    obj,
    *keys
):
    current = obj

    for key in keys:
        if not isinstance(
            current,
            dict
        ):
            return None

        current = current.get(
            key
        )

    return current


def first_nonempty(
    *values
):
    for value in values:
        if value not in (
            None,
            "",
            []
        ):
            return value

    return None


def normalize_published_at(
    value
):
    if value is None:
        return None

    if isinstance(
        value,
        (
            int,
            float
        )
    ):
        try:
            return datetime.fromtimestamp(
                value,
                tz=timezone.utc
            ).isoformat()

        except Exception:
            return None

    text = str(
        value
    ).strip()

    return (
        text
        if text
        else None
    )


def fetch_news_records(
    ticker,
    count=NEWS_COUNT
):
    raw_news = []

    try:
        search = yf.Search(
            ticker,
            max_results=1,
            news_count=count,
            lists_count=0,
            recommended=0,
            raise_errors=False
        )

        raw_news = (
            search.news
            or
            []
        )

    except Exception:
        raw_news = []

    if not raw_news:
        try:
            raw_news = (
                yf.Ticker(
                    ticker
                ).news
                or
                []
            )

        except Exception:
            raw_news = []

    records = []
    scoring_text = []

    for article in raw_news[
        :count
    ]:
        if not isinstance(
            article,
            dict
        ):
            continue

        content = (
            article.get(
                "content"
            )
            if isinstance(
                article.get(
                    "content"
                ),
                dict
            )
            else {}
        )

        related = first_nonempty(
            article.get(
                "relatedTickers"
            ),
            content.get(
                "relatedTickers"
            ),
            []
        )

        if (
            related
            and
            ticker
            not in related
        ):
            continue

        title = first_nonempty(
            article.get(
                "title"
            ),
            content.get(
                "title"
            ),
            ""
        )

        summary = first_nonempty(
            article.get(
                "summary"
            ),
            content.get(
                "summary"
            ),
            content.get(
                "description"
            ),
            ""
        )

        source = first_nonempty(
            article.get(
                "publisher"
            ),
            nested_value(
                content,
                "provider",
                "displayName"
            ),
            nested_value(
                content,
                "provider",
                "name"
            )
        )

        url = first_nonempty(
            article.get(
                "link"
            ),
            nested_value(
                content,
                "canonicalUrl",
                "url"
            ),
            nested_value(
                content,
                "clickThroughUrl",
                "url"
            )
        )

        published_at = normalize_published_at(
            first_nonempty(
                article.get(
                    "providerPublishTime"
                ),
                content.get(
                    "pubDate"
                ),
                content.get(
                    "displayTime"
                )
            )
        )

        title = str(
            title
            or
            ""
        ).strip()

        summary = str(
            summary
            or
            ""
        ).strip()

        if not title:
            continue

        scoring_text.append(
            (
                title
                +
                " "
                +
                summary
            ).strip()
        )

        # Archive headline-level metadata only; article body/summary is not
        # persisted. Summary may still be used transiently for scoring above.
        records.append({
            "headline":
            title,

            "source":
            source,

            "url":
            url,

            "published_at":
            published_at,

            "related_tickers":
            related
            if isinstance(
                related,
                list
            )
            else []
        })

    return (
        records,
        scoring_text
    )


def archive_ticker(
    ticker,
    retrieval_time
):
    news_records = []
    scoring_text = []
    errors = []

    try:
        (
            news_records,
            scoring_text
        ) = fetch_news_records(
            ticker
        )

    except Exception as error:
        errors.append(
            "NEWS:"
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

    try:
        fundamental = analyze_fundamental_thesis(
            ticker
        )

    except Exception as error:
        fundamental = {
            "ticker":
            ticker,

            "data_quality":
            "ERROR",

            "error":
            str(
                error
            )
        }

        errors.append(
            "FUNDAMENTAL:"
            +
            str(
                error
            )
        )

    return {
        "ticker":
        ticker,

        "retrieved_at":
        retrieval_time,

        "news_headlines":
        news_records,

        "news_analysis":
        news_result,

        "catalyst_analysis":
        catalyst_result,

        "fundamental_snapshot":
        fundamental,

        "errors":
        errors
    }


def run_daily_evidence_archive():
    now = datetime.now(
        timezone.utc
    )

    archive_date = (
        now.date().isoformat()
    )

    retrieval_time = (
        now.isoformat()
    )

    tickers = load_tickers()

    records = []

    for ticker in tickers:
        records.append(
            archive_ticker(
                ticker,
                retrieval_time
            )
        )

    news_live = sum(
        1
        for item in records
        if (
            (
                item.get(
                    "news_analysis",
                    {}
                )
                or
                {}
            ).get(
                "data_quality"
            )
            ==
            "LIVE"
        )
    )

    fundamental_good_or_partial = sum(
        1
        for item in records
        if (
            (
                item.get(
                    "fundamental_snapshot",
                    {}
                )
                or
                {}
            ).get(
                "data_quality"
            )
            in {
                "GOOD",
                "PARTIAL"
            }
        )
    )

    error_tickers = [
        item.get(
            "ticker"
        )
        for item in records
        if item.get(
            "errors"
        )
    ]

    result = {
        "engine":
        ENGINE_VERSION,

        "archive_signature":
        ARCHIVE_SIGNATURE,

        "archive_date":
        archive_date,

        "retrieved_at":
        retrieval_time,

        "status":
        "COMPLETE",

        "point_in_time_forward_archive":
        True,

        "live_decisions_changed":
        False,

        "paper_order_submission_authorized":
        False,

        "live_execution_authorized":
        False,

        "universe": {
            "source":
            (
                "Union of data/us_universe.json and "
                "data/portfolio.csv"
            ),

            "ticker_count":
            len(
                tickers
            )
        },

        "coverage": {
            "news_live_tickers":
            news_live,

            "fundamental_good_or_partial_tickers":
            fundamental_good_or_partial,

            "error_ticker_count":
            len(
                error_tickers
            ),

            "error_tickers":
            error_tickers
        },

        "archive_policy": {
            "news_article_body_stored":
            False,

            "news_summary_stored":
            False,

            "headline_metadata_stored":
            True,

            "news_and_catalyst_scores_stored":
            True,

            "current_fundamental_snapshot_stored":
            True,

            "future_sec_edgar_extension_planned":
            True
        },

        "records":
        records
    }

    os.makedirs(
        ARCHIVE_DIR,
        exist_ok=True
    )

    output_file = os.path.join(
        ARCHIVE_DIR,
        archive_date
        +
        ".json"
    )

    with open(
        output_file,
        "w",
        encoding="utf-8"
    ) as file:
        json.dump(
            result,
            file,
            indent=2,
            ensure_ascii=False
        )

    latest_file = os.path.join(
        ARCHIVE_DIR,
        "latest.json"
    )

    with open(
        latest_file,
        "w",
        encoding="utf-8"
    ) as file:
        json.dump(
            result,
            file,
            indent=2,
            ensure_ascii=False
        )

    return (
        result,
        output_file,
        latest_file
    )
