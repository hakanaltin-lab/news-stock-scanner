import csv
import json
import os

from engines.sec_edgar_point_in_time_engine import (
    ENGINE_VERSION,
    SIGNATURE,
    SECClient,
    fetch_ticker_facts,
    load_sec_ticker_map,
    normalize_ticker
)


UNIVERSE_FILE = "data/us_universe.json"
PORTFOLIO_FILE = "data/portfolio.csv"
OUTPUT_DIR = "data/sec_edgar_pit/facts"
SUMMARY_FILE = "data/sec_edgar_pit/latest_summary.json"


def load_current_evidence_universe():
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

    return sorted(
        tickers
    )


def canonical_json(
    value
):
    return json.dumps(
        value,
        indent=2,
        sort_keys=True,
        ensure_ascii=False
    ) + "\n"


def write_if_changed(
    path,
    value
):
    content = canonical_json(
        value
    )

    existing = None

    if os.path.exists(
        path
    ):
        try:
            with open(
                path,
                "r",
                encoding="utf-8"
            ) as file:
                existing = file.read()

        except Exception:
            existing = None

    if existing == content:
        return False

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
        file.write(
            content
        )

    return True


def main():
    user_agent = os.getenv(
        "SEC_USER_AGENT",
        ""
    ).strip()

    if not user_agent:
        print(
            json.dumps({
                "engine":
                ENGINE_VERSION,

                "signature":
                SIGNATURE,

                "status":
                "DISABLED_MISSING_SEC_USER_AGENT",

                "required_environment_variable":
                "SEC_USER_AGENT",

                "live_decisions_changed":
                False
            },
            indent=2)
        )

        return 0

    client = SECClient(
        user_agent=user_agent
    )

    ticker_map = load_sec_ticker_map(
        client
    )

    tickers = load_current_evidence_universe()

    results = []
    changed_files = 0

    for ticker in tickers:
        try:
            result = fetch_ticker_facts(
                client,
                ticker,
                ticker_map
            )

        except Exception as error:
            result = {
                "engine":
                ENGINE_VERSION,

                "signature":
                SIGNATURE,

                "ticker":
                ticker,

                "status":
                "ERROR",

                "error":
                str(
                    error
                ),

                "point_in_time":
                True,

                "facts":
                []
            }

        output_path = os.path.join(
            OUTPUT_DIR,
            ticker
            +
            ".json"
        )

        if write_if_changed(
            output_path,
            result
        ):
            changed_files += 1

        results.append({
            "ticker":
            ticker,

            "status":
            result.get(
                "status"
            ),

            "fact_count":
            result.get(
                "fact_count",
                0
            ),

            "accession_count":
            result.get(
                "accession_count",
                0
            ),

            "latest_available_date":
            result.get(
                "latest_available_date"
            )
        })

    status_counts = {}

    for row in results:
        status = row.get(
            "status"
        )

        status_counts[
            status
        ] = (
            status_counts.get(
                status,
                0
            )
            +
            1
        )

    summary = {
        "engine":
        ENGINE_VERSION,

        "signature":
        SIGNATURE,

        "status":
        "COMPLETE",

        "scope":
        (
            "Current evidence universe only; full PIT S&P500 + Nasdaq100 "
            "expansion is the next milestone."
        ),

        "ticker_count":
        len(
            tickers
        ),

        "changed_fact_files":
        changed_files,

        "status_counts":
        status_counts,

        "records":
        results,

        "point_in_time":
        True,

        "live_decisions_changed":
        False,

        "paper_order_submission_authorized":
        False,

        "live_execution_authorized":
        False
    }

    write_if_changed(
        SUMMARY_FILE,
        summary
    )

    print(
        json.dumps(
            summary,
            indent=2
        )
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
