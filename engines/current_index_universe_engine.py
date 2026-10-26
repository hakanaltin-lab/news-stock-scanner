"""
AURORA Current Index Universe Snapshot

Builds a forward-looking, timestamped current constituent snapshot for:
- S&P 500
- Nasdaq-100

Source methodology mirrors the structured-table parsing used by the pinned
thuningxu/sp500nq100 research source, but this engine is forward-only and fetches
the current Wikipedia wikitext at run time.

This module does not reconstruct history and does not affect live portfolio
decisions. Its output is an evidence-universe source for SEC/news archiving.
"""

from datetime import datetime, timezone
from io import StringIO
import json
import os
import re

import pandas as pd
import requests


ENGINE_VERSION = "V8.8.1 Current Index Universe Snapshot"
SIGNATURE = "V8.8.1"

SP500_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"

NASDAQ100_URL = (
    "https://en.wikipedia.org/wiki/List_of_NASDAQ-100_companies"
)

USER_AGENT = (
    "AURORA-index-universe-snapshot/1.0 "
    "(research evidence archive; GitHub: hakanaltin-lab/news-stock-scanner)"
)

REQUEST_TIMEOUT_SECONDS = 45

_RE_REF_SELF = re.compile(
    r"<ref[^>]*?/>",
    re.IGNORECASE
)

_RE_REF_PAIR = re.compile(
    r"<ref[^>]*?>.*?</ref\s*>",
    re.DOTALL | re.IGNORECASE
)

_RE_COMMENT = re.compile(
    r"<!--.*?-->",
    re.DOTALL
)

_RE_CELL_SEP = re.compile(
    r"(?:\n\s*\|)|(?:\|\|)"
)

_RE_WIKILINK = re.compile(
    r"\[\[(?:[^\]|]*\|)?([^\]|]*)\]\]"
)

_RE_SP_SYMBOL = re.compile(
    r"\{\{(?:[A-Za-z]+Symbol|BZX link)\|\s*([^}|]+?)\s*\}\}"
)


def strip_refs(
    value
):
    value = _RE_REF_SELF.sub(
        "",
        value
    )

    value = _RE_REF_PAIR.sub(
        "",
        value
    )

    return _RE_COMMENT.sub(
        "",
        value
    )


def clean_ticker(
    cell
):
    cell = strip_refs(
        str(
            cell
            or
            ""
        )
    )

    match = _RE_WIKILINK.search(
        cell
    )

    if match:
        cell = match.group(
            1
        )

    cell = (
        cell
        .replace(
            "'''",
            ""
        )
        .replace(
            "''",
            ""
        )
        .strip()
    )

    match = re.match(
        r"[A-Za-z0-9.\-]+",
        cell
    )

    ticker = (
        match.group(
            0
        ).upper()
        if match
        else ""
    )

    # Normalize to the dash convention used by yfinance / AURORA.
    return ticker.replace(
        ".",
        "-"
    )


def extract_table(
    wikitext,
    table_id
):
    lines = wikitext.splitlines()
    start = None

    for index, line in enumerate(
        lines
    ):
        if (
            line.lstrip().startswith(
                "{|"
            )
            and
            f'id="{table_id}"'
            in line
        ):
            start = index
            break

    if start is None:
        raise ValueError(
            f'table id="{table_id}" not found'
        )

    for index in range(
        start + 1,
        len(
            lines
        )
    ):
        if lines[
            index
        ].strip() == "|}":
            return "\n".join(
                lines[
                    start:
                    index + 1
                ]
            )

    raise ValueError(
        f'table id="{table_id}" not closed'
    )


def split_cells(
    chunk
):
    chunk = chunk.strip()

    if chunk.startswith(
        "|"
    ):
        chunk = chunk[
            1:
        ]

    return [
        item.strip()
        for item in _RE_CELL_SEP.split(
            chunk
        )
    ]


def flatten_columns(
    frame
):
    if isinstance(
        frame.columns,
        pd.MultiIndex
    ):
        frame.columns = [
            " ".join(
                str(
                    part
                )
                for part in column
                if str(
                    part
                )
                not in {
                    "",
                    "nan"
                }
            ).strip()
            for column in frame.columns
        ]

    else:
        frame.columns = [
            str(
                column
            ).strip()
            for column in frame.columns
        ]

    return frame


def choose_component_table(
    html,
    ticker_column_candidates,
    min_rows
):
    tables = pd.read_html(
        StringIO(
            html
        )
    )

    for frame in tables:
        frame = flatten_columns(
            frame
        )

        columns = {
            str(
                column
            ).strip().lower():
            column
            for column in frame.columns
        }

        selected_column = None

        for candidate in ticker_column_candidates:
            if candidate.lower() in columns:
                selected_column = columns[
                    candidate.lower()
                ]
                break

        if selected_column is None:
            continue

        if len(
            frame
        ) < min_rows:
            continue

        return (
            frame,
            selected_column
        )

    raise ValueError(
        "Current constituent table not found in Wikipedia HTML."
    )


def parse_current_table(
    html,
    ticker_column_candidates,
    min_rows
):
    (
        frame,
        ticker_column
    ) = choose_component_table(
        html,
        ticker_column_candidates,
        min_rows
    )

    tickers = []

    for value in frame[
        ticker_column
    ].tolist():
        ticker = clean_ticker(
            value
        )

        if re.fullmatch(
            r"[A-Z][A-Z0-9\-]*",
            ticker
            or
            ""
        ):
            tickers.append(
                ticker
            )

    return sorted(
        set(
            tickers
        )
    )


def fetch_text(
    url
):
    response = requests.get(
        url,
        timeout=REQUEST_TIMEOUT_SECONDS,
        headers={
            "User-Agent":
            USER_AGENT
        }
    )

    response.raise_for_status()

    return response.text



def build_current_index_universe():
    retrieved_at = datetime.now(
        timezone.utc
    )

    sp_text = fetch_text(
        SP500_URL
    )

    nq_text = fetch_text(
        NASDAQ100_URL
    )

    sp500 = parse_current_table(
        sp_text,
        [
            "Symbol"
        ],
        490
    )

    nasdaq100 = parse_current_table(
        nq_text,
        [
            "Ticker"
        ],
        95
    )

    sp500_missed = []

    union = sorted(
        set(
            sp500
        )
        |
        set(
            nasdaq100
        )
    )

    if len(
        sp500
    ) < 490:
        raise ValueError(
            "S&P 500 current constituent parse returned fewer than 490 symbols."
        )

    if not (
        95
        <=
        len(
            nasdaq100
        )
        <=
        105
    ):
        raise ValueError(
            "Nasdaq-100 current constituent parse returned an implausible count."
        )

    if len(
        union
    ) < 500:
        raise ValueError(
            "Combined current index universe is implausibly small."
        )

    return {
        "engine":
        ENGINE_VERSION,

        "signature":
        SIGNATURE,

        "status":
        "COMPLETE",

        "retrieved_at":
        retrieved_at.isoformat(),

        "snapshot_date_utc":
        retrieved_at.date().isoformat(),

        "forward_snapshot":
        True,

        "historical_reconstruction":
        False,

        "sources": {
            "sp500":
            SP500_URL,

            "nasdaq100":
            NASDAQ100_URL,

            "methodology_reference":
            (
                "Current Wikipedia component tables parsed from HTML by named "
                "ticker columns. Historical validation remains separate."
            )
        },

        "counts": {
            "sp500":
            len(
                sp500
            ),

            "nasdaq100":
            len(
                nasdaq100
            ),

            "union":
            len(
                union
            ),

            "sp500_unparsed_rows":
            len(
                sp500_missed
            )
        },

        "sp500":
        sp500,

        "nasdaq100":
        nasdaq100,

        "union":
        union,

        "live_decisions_changed":
        False,

        "paper_order_submission_authorized":
        False,

        "live_execution_authorized":
        False
    }


def write_snapshot(
    result,
    directory="data/current_index_universe"
):
    os.makedirs(
        directory,
        exist_ok=True
    )

    dated_file = os.path.join(
        directory,
        str(
            result.get(
                "snapshot_date_utc"
            )
        )
        +
        ".json"
    )

    latest_file = os.path.join(
        directory,
        "latest.json"
    )

    content = json.dumps(
        result,
        indent=2,
        ensure_ascii=False,
        sort_keys=True
    ) + "\n"

    for path in [
        dated_file,
        latest_file
    ]:
        with open(
            path,
            "w",
            encoding="utf-8"
        ) as file:
            file.write(
                content
            )

    return (
        dated_file,
        latest_file
    )
