import csv
import json
import os
import tempfile

from engines.sec_archive_quality_engine import (
    build_archive_summary, curate_sec_record, inspect_sec_record,
)

from engines.sec_edgar_point_in_time_engine import (
    CANONICAL_METRICS,
    SECClient,
    fetch_ticker_facts,
    load_sec_ticker_map,
    normalize_ticker
)


UNIVERSE_FILE = "data/us_universe.json"
PORTFOLIO_FILE = "data/portfolio.csv"
CURRENT_INDEX_UNIVERSE_FILE = "data/current_index_universe/latest.json"
OUTPUT_DIR = "data/sec_edgar_pit/facts"
QUARANTINE_DIR = "data/sec_edgar_pit/quarantine"
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


def canonical_json(value):
    return json.dumps(
        value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False
    ) + "\n"


def write_if_changed(path, value):
    content = canonical_json(value)
    try:
        with open(path, "r", encoding="utf-8") as file:
            if file.read() == content:
                return False
    except (OSError, UnicodeError):
        pass

    directory = os.path.dirname(path) or "."
    os.makedirs(directory, exist_ok=True)
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=directory, delete=False
        ) as file:
            temporary_path = file.name
            file.write(content)
        os.replace(temporary_path, path)
    finally:
        if temporary_path and os.path.exists(temporary_path):
            os.unlink(temporary_path)
    return True


def load_existing_record(path):
    try:
        with open(path, "r", encoding="utf-8") as file:
            record = json.load(file)
        return record if isinstance(record, dict) else {}
    except (OSError, ValueError, UnicodeError):
        return {}


def finish_run(summary, exit_code):
    write_if_changed(SUMMARY_FILE, summary)
    # A compact, public-safe source-status file. Never copy the User-Agent.
    dashboard = {
        key: value for key, value in summary.items()
        if key not in {"records", "unattempted_tickers"}
    }
    write_if_changed("docs/sec_archive_readiness.json", dashboard)

    output_path = os.getenv("GITHUB_OUTPUT")
    if output_path:
        with open(output_path, "a", encoding="utf-8") as file:
            file.write("status=" + summary["status"] + "\n")

    summary_path = os.getenv("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as file:
            file.write(
                "## SEC archive data readiness\n\n"
                + "**Status: " + summary["status"] + "**\n\n"
                + "Usable tickers this run: "
                + str(summary["usable_ticker_count"]) + "/"
                + str(summary["ticker_count"]) + ".\n\n"
                + "Setup blockers and failed collection are not successful archives. "
                + "Retained older facts do not count as current-run coverage.\n\n"
                + "Fundamental research use, paper orders and LIVE execution "
                + "remain unauthorized.\n"
            )

    if os.getenv("GITHUB_ACTIONS") == "true" and not summary["collection_ready"]:
        print("::error::SEC archive is not data-ready: " + summary["status"])
    elif os.getenv("GITHUB_ACTIONS") == "true" and summary["status"] == "COMPLETE_WITH_GAPS":
        print("::warning::SEC archive completed with coverage gaps; inspect the readiness report.")
    print(json.dumps(summary, indent=2, allow_nan=False))
    return exit_code


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
    tickers, universe_source = load_current_evidence_universe()
    user_agent = os.getenv("SEC_USER_AGENT", "").strip()

    if not user_agent:
        return finish_run(build_archive_summary(
            tickers, universe_source, [],
            status="DISABLED_MISSING_SEC_USER_AGENT"
        ), 2)

    if not tickers:
        return finish_run(build_archive_summary(
            tickers, universe_source, [], status="BLOCKED_EMPTY_UNIVERSE"
        ), 1)

    # Bootstrap failures also produce a visible status, without publishing
    # request headers, the contact address, or potentially sensitive exceptions.
    try:
        client = SECClient(user_agent=user_agent)
        ticker_map = load_sec_ticker_map(client)
        if not ticker_map:
            return finish_run(build_archive_summary(
                tickers, universe_source, [],
                status="BLOCKED_EMPTY_SEC_TICKER_MAP", ticker_map={}
            ), 1)
    except Exception as error:
        return finish_run(build_archive_summary(
            tickers, universe_source, [], status="ERROR_SEC_TICKER_MAP",
            error_type=type(error).__name__
        ), 1)

    results = []
    changed_files = 0
    for ticker in tickers:
        try:
            result = fetch_ticker_facts(client, ticker, ticker_map)
        except Exception as error:
            result = {
                "ticker": ticker,
                "cik": (ticker_map.get(ticker) or {}).get("cik"),
                "status": "ERROR",
                "error_type": type(error).__name__,
                "facts": [],
            }

        result, quarantine = curate_sec_record(result)
        if quarantine is not None:
            quarantine_path = os.path.join(QUARANTINE_DIR, ticker + ".json")
            write_if_changed(quarantine_path, quarantine)
            if result.get("quality_curation"):
                result["quality_curation"]["quarantine_file"] = quarantine_path
        row = inspect_sec_record(result)
        if quarantine is not None:
            row["quarantined_fact_count"] = quarantine["quarantined_fact_count"]
            row["quarantine_file"] = quarantine_path
        output_path = os.path.join(OUTPUT_DIR, ticker + ".json")
        previous = load_existing_record(output_path)
        row["retained_previous_evidence"] = False
        if row["quality_valid"]:
            if write_if_changed(output_path, result):
                changed_files += 1
        else:
            # A failed/empty/invalid fetch must never replace good evidence.
            row["retained_previous_evidence"] = inspect_sec_record(previous)["quality_valid"]
        if result.get("error_type"):
            row["error_type"] = result["error_type"]
        results.append(row)

    summary = build_archive_summary(
        tickers, universe_source, results, ticker_map=ticker_map,
        changed_fact_files=changed_files
    )
    # Keep the earlier telemetry schema, but never count rejected candidate
    # facts as usable data. Failed issuers still remain in the denominator.
    quality_results = [
        row if row["quality_valid"] else {
            "ticker": row["ticker"], "cik": row["cik"],
            "status": row["status"],
            "submissions_metadata": row["submissions_metadata"],
        }
        for row in results
    ]
    summary["quality_summary"] = build_quality_summary(quality_results)
    return finish_run(summary, 0 if summary["collection_ready"] else 1)


if __name__ == "__main__":
    raise SystemExit(main())
