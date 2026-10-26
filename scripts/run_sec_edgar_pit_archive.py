import csv
from datetime import datetime, timezone
import json
import os

from engines.sec_edgar_point_in_time_engine import (
    CANONICAL_METRICS,
    ENGINE_VERSION,
    SIGNATURE,
    SECClient,
    fetch_ticker_facts,
    load_sec_ticker_map,
    normalize_ticker
)


UNIVERSE_FILE = "data/us_universe.json"
PORTFOLIO_FILE = "data/portfolio.csv"
CURRENT_INDEX_UNIVERSE_FILE = "data/current_index_universe/latest.json"
OUTPUT_DIR = "data/sec_edgar_pit/facts"
SUMMARY_FILE = "data/sec_edgar_pit/latest_summary.json"


def load_current_evidence_universe():
    tickers = set()
    source = "CORE_65_FALLBACK"

    try:
        with open(
            CURRENT_INDEX_UNIVERSE_FILE,
            "r",
            encoding="utf-8"
        ) as file:
            current_index = json.load(
                file
            )

        union = (
            current_index.get(
                "union",
                []
            )
            or
            []
        )

        for item in union:
            ticker = normalize_ticker(
                item
            )

            if ticker:
                tickers.add(
                    ticker
                )

        if tickers:
            source = "CURRENT_SP500_NASDAQ100_UNION"

    except Exception:
        pass

    # Always include current AURORA portfolio / scanner names even when they
    # fall outside the two benchmark universes.
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

    return (
        sorted(
            tickers
        ),
        source
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


def percentage(
    numerator,
    denominator
):
    if not denominator:
        return 0.0

    return round(
        numerator
        /
        denominator
        *
        100.0,
        2
    )


def build_quality_summary(
    results
):
    ticker_count = len(
        results
    )

    cik_mapped_count = sum(
        1
        for result in results
        if result.get(
            "cik"
        )
    )

    fact_ticker_count = sum(
        1
        for result in results
        if result.get(
            "fact_count",
            0
        )
        >
        0
    )

    exact_acceptance_ticker_count = sum(
        1
        for result in results
        if result.get(
            "exact_acceptance_fact_count",
            0
        )
        >
        0
    )

    total_fact_count = sum(
        result.get(
            "fact_count",
            0
        )
        or
        0
        for result in results
    )

    exact_acceptance_fact_count = sum(
        result.get(
            "exact_acceptance_fact_count",
            0
        )
        or
        0
        for result in results
    )

    amendment_fact_count = sum(
        result.get(
            "amendment_fact_count",
            0
        )
        or
        0
        for result in results
    )

    metric_ticker_counts = {
        metric:
        0
        for metric in CANONICAL_METRICS
    }

    taxonomy_ticker_counts = {}
    taxonomy_fact_counts = {}
    historical_files_loaded = 0
    historical_files_failed = 0
    submissions_status_counts = {}

    for result in results:
        present_metrics = (
            (
                result.get(
                    "metric_coverage",
                    {}
                )
                or
                {}
            ).get(
                "present_metrics",
                []
            )
            or
            []
        )

        for metric in set(
            present_metrics
        ):
            metric_ticker_counts[
                metric
            ] = (
                metric_ticker_counts.get(
                    metric,
                    0
                )
                +
                1
            )

        ticker_taxonomies = (
            result.get(
                "taxonomy_fact_counts",
                {}
            )
            or
            {}
        )

        for namespace, fact_count in (
            ticker_taxonomies.items()
        ):
            taxonomy_ticker_counts[
                namespace
            ] = (
                taxonomy_ticker_counts.get(
                    namespace,
                    0
                )
                +
                1
            )

            taxonomy_fact_counts[
                namespace
            ] = (
                taxonomy_fact_counts.get(
                    namespace,
                    0
                )
                +
                (
                    fact_count
                    or
                    0
                )
            )

        submissions = (
            result.get(
                "submissions_metadata",
                {}
            )
            or
            {}
        )

        submissions_status = submissions.get(
            "status",
            "NOT_AVAILABLE"
        ) or "NOT_AVAILABLE"

        submissions_status_counts[
            submissions_status
        ] = (
            submissions_status_counts.get(
                submissions_status,
                0
            )
            +
            1
        )

        historical_files_loaded += (
            submissions.get(
                "historical_files_loaded",
                0
            )
            or
            0
        )

        historical_files_failed += (
            submissions.get(
                "historical_files_failed",
                0
            )
            or
            0
        )

    metric_coverage_pct = {
        metric:
        percentage(
            count,
            ticker_count
        )
        for metric, count in sorted(
            metric_ticker_counts.items()
        )
    }

    return {
        "measurement_status":
        "OBSERVATION_ONLY_NO_ALPHA_GATE",

        "ticker_count":
        ticker_count,

        "cik_mapped_count":
        cik_mapped_count,

        "cik_coverage_pct":
        percentage(
            cik_mapped_count,
            ticker_count
        ),

        "fact_ticker_count":
        fact_ticker_count,

        "fact_ticker_coverage_pct":
        percentage(
            fact_ticker_count,
            ticker_count
        ),

        "metric_ticker_counts":
        dict(
            sorted(
                metric_ticker_counts.items()
            )
        ),

        "metric_ticker_coverage_pct":
        metric_coverage_pct,

        "taxonomy_ticker_counts":
        dict(
            sorted(
                taxonomy_ticker_counts.items()
            )
        ),

        "taxonomy_fact_counts":
        dict(
            sorted(
                taxonomy_fact_counts.items()
            )
        ),

        "total_fact_count":
        total_fact_count,

        "exact_acceptance_ticker_count":
        exact_acceptance_ticker_count,

        "exact_acceptance_fact_count":
        exact_acceptance_fact_count,

        "exact_acceptance_fact_coverage_pct":
        percentage(
            exact_acceptance_fact_count,
            total_fact_count
        ),

        "amendment_fact_count":
        amendment_fact_count,

        "historical_submission_files_loaded":
        historical_files_loaded,

        "historical_submission_files_failed":
        historical_files_failed,

        "submissions_status_counts":
        dict(
            sorted(
                submissions_status_counts.items()
            )
        ),

        "automatic_alpha_use_authorized":
        False,

        "next_gate":
        (
            "Review observed coverage and concept continuity before freezing "
            "a separate pre-registered fundamental research protocol."
        )
    }


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

        # Fail closed so GitHub Actions cannot report a false-successful SEC
        # archive when the required fair-access identity is absent.
        return 2

    client = SECClient(
        user_agent=user_agent
    )

    ticker_map = load_sec_ticker_map(
        client
    )

    (
        tickers,
        universe_source
    ) = load_current_evidence_universe()

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
            ticker_mapping = (
                ticker_map.get(
                    ticker,
                    {}
                )
                or
                {}
            )

            result = {
                "engine":
                ENGINE_VERSION,

                "signature":
                SIGNATURE,

                "ticker":
                ticker,

                "cik":
                ticker_mapping.get(
                    "cik"
                ),

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
            ),

            "cik":
            result.get(
                "cik"
            ),

            "metric_coverage":
            result.get(
                "metric_coverage",
                {}
            ),

            "taxonomy_fact_counts":
            result.get(
                "taxonomy_fact_counts",
                {}
            ),

            "exact_acceptance_fact_count":
            result.get(
                "exact_acceptance_fact_count",
                0
            ),

            "amendment_fact_count":
            result.get(
                "amendment_fact_count",
                0
            ),

            "submissions_metadata":
            {
                key:
                (
                    result.get(
                        "submissions_metadata",
                        {}
                    )
                    or
                    {}
                ).get(
                    key
                )
                for key in [
                    "status",
                    "historical_cutoff_date",
                    "recent_acceptance_count",
                    "historical_acceptance_count",
                    "total_acceptance_count",
                    "historical_files_discovered",
                    "historical_files_loaded",
                    "historical_files_failed"
                ]
            }
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

        "generated_at":
        datetime.now(
            timezone.utc
        ).isoformat(),

        "scope":
        (
            "Current S&P500 + Nasdaq100 union when the forward universe "
            "snapshot is available, plus AURORA scanner/portfolio names."
        ),

        "universe_source":
        universe_source,

        "ticker_count":
        len(
            tickers
        ),

        "changed_fact_files":
        changed_files,

        "status_counts":
        status_counts,

        "quality_summary":
        build_quality_summary(
            results
        ),

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
