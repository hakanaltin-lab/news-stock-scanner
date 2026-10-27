import json
from datetime import date, timedelta

from engines.sec_edgar_point_in_time_engine import (
    build_snapshot_as_of,
    historical_submission_files,
    load_acceptance_metadata,
    normalize_companyfacts
)
from scripts.run_sec_edgar_pit_archive import build_quality_summary


def assert_equal(
    actual,
    expected,
    message
):
    if actual != expected:
        raise AssertionError(
            f"{message}: expected={expected!r} actual={actual!r}"
        )


class FakeSECClient:
    def __init__(
        self,
        responses
    ):
        self.responses = responses
        self.requested_urls = []


    def get_json(
        self,
        url
    ):
        self.requested_urls.append(
            url
        )

        if url not in self.responses:
            raise AssertionError(
                f"Unexpected SEC URL requested: {url}"
            )

        response = self.responses[
            url
        ]

        if isinstance(
            response,
            Exception
        ):
            raise response

        return response


def main():
    payload = {
        "entityName":
        "Synthetic Corp",

        "facts": {
            "us-gaap": {
                "RevenueFromContractWithCustomerExcludingAssessedTax": {
                    "units": {
                        "USD": [
                            {
                                "val": 100,
                                "start": "2020-01-01",
                                "end": "2020-03-31",
                                "filed": "2020-05-01",
                                "form": "10-Q",
                                "fy": 2020,
                                "fp": "Q1",
                                "accn": "0000000000-20-000001",
                                "frame": "CY2020Q1"
                            },
                            {
                                "val": 110,
                                "start": "2020-01-01",
                                "end": "2020-03-31",
                                "filed": "2020-05-20",
                                "form": "10-Q/A",
                                "fy": 2020,
                                "fp": "Q1",
                                "accn": "0000000000-20-000002",
                                "frame": "CY2020Q1"
                            }
                        ]
                    }
                }
            },

            "ifrs-full": {
                "Revenue": {
                    "units": {
                        "EUR": [
                            {
                                "val": 200,
                                "start": "2019-01-01",
                                "end": "2019-12-31",
                                "filed": "2020-02-15",
                                "form": "20-F",
                                "fy": 2019,
                                "fp": "FY",
                                "accn": "0000000000-20-000003",
                                "frame": "CY2019"
                            }
                        ]
                    }
                }
            }
        }
    }

    acceptance_map = {
        "0000000000-20-000001": {
            "accepted_at":
            "2020-05-01T16:00:00.000Z"
        },

        "0000000000-20-000002": {
            "accepted_at":
            "2020-05-20T16:00:00.000Z"
        },

        "0000000000-20-000003": {
            "accepted_at":
            "2020-02-15T09:00:00.000Z"
        }
    }

    record = normalize_companyfacts(
        "TEST",
        "1",
        payload,
        acceptance_map=acceptance_map
    )

    before_amendment = build_snapshot_as_of(
        record,
        "2020-05-02"
    )

    after_amendment = build_snapshot_as_of(
        record,
        "2020-05-21"
    )

    early_ifrs = build_snapshot_as_of(
        record,
        "2020-02-16",
        duration_period="annual"
    )

    assert_equal(
        before_amendment[
            "metrics"
        ][
            "revenue"
        ][
            "value"
        ],
        100,
        "Original filing must be visible before amendment availability"
    )

    assert_equal(
        before_amendment[
            "metrics"
        ][
            "revenue"
        ][
            "namespace"
        ],
        "us-gaap",
        "US GAAP namespace should be preserved"
    )

    assert_equal(
        after_amendment[
            "metrics"
        ][
            "revenue"
        ][
            "value"
        ],
        110,
        "Amended filing must replace the earlier value only after availability"
    )

    assert_equal(
        after_amendment[
            "metrics"
        ][
            "revenue"
        ][
            "accepted_at"
        ],
        "2020-05-20T16:00:00.000Z",
        "SEC acceptance timestamp should be retained"
    )

    assert_equal(
        early_ifrs[
            "metrics"
        ][
            "revenue"
        ][
            "value"
        ],
        200,
        "IFRS revenue should normalize into canonical revenue"
    )

    assert_equal(
        early_ifrs[
            "metrics"
        ][
            "revenue"
        ][
            "namespace"
        ],
        "ifrs-full",
        "IFRS namespace should be preserved"
    )

    assert_equal(
        record[
            "metric_coverage"
        ][
            "present_metrics"
        ],
        [
            "revenue"
        ],
        "Canonical metric coverage should be explicit"
    )

    assert_equal(
        record[
            "taxonomy_fact_counts"
        ],
        {
            "ifrs-full":
            1,

            "us-gaap":
            2
        },
        "Taxonomy coverage should count normalized facts"
    )

    assert_equal(
        record[
            "exact_acceptance_fact_count"
        ],
        3,
        "Exact acceptance coverage should count matched accessions"
    )

    submissions_url = (
        "https://data.sec.gov/submissions/CIK0000000001.json"
    )

    current_payload = {
        "filings": {
            "recent": {
                "accessionNumber": [
                    "0000000001-24-000001"
                ],
                "acceptanceDateTime": [
                    "2024-05-01T16:00:00.000Z"
                ],
                "filingDate": [
                    "2024-05-01"
                ],
                "form": [
                    "10-Q"
                ]
            },
            "files": [
                {
                    "name":
                    "CIK0000000001-submissions-001.json",
                    "filingFrom":
                    "2012-01-01",
                    "filingTo":
                    "2023-12-31"
                },
                {
                    "name":
                    "CIK0000000001-submissions-002.json",
                    "filingFrom":
                    "1995-01-01",
                    "filingTo":
                    "2008-12-31"
                },
                {
                    "name":
                    "../unsafe.json",
                    "filingFrom":
                    "2020-01-01",
                    "filingTo":
                    "2020-12-31"
                }
            ]
        }
    }

    historical_payload = {
        "accessionNumber": [
            "0000000001-20-000001"
        ],
        "acceptanceDateTime": [
            "2020-05-01T16:00:00.000Z"
        ],
        "filingDate": [
            "2020-05-01"
        ],
        "form": [
            "10-Q"
        ]
    }

    historical_url = (
        "https://data.sec.gov/submissions/"
        "CIK0000000001-submissions-001.json"
    )

    eligible_files = historical_submission_files(
        current_payload
    )

    assert_equal(
        [
            item[
                "name"
            ]
            for item in eligible_files
        ],
        [
            "CIK0000000001-submissions-001.json"
        ],
        "Only safe XBRL-era historical submission files should be fetched"
    )

    fake_client = FakeSECClient({
        submissions_url:
        current_payload,

        historical_url:
        historical_payload
    })

    (
        full_acceptance_map,
        submissions_metadata
    ) = load_acceptance_metadata(
        fake_client,
        "1"
    )

    assert_equal(
        sorted(
            full_acceptance_map
        ),
        [
            "0000000001-20-000001",
            "0000000001-24-000001"
        ],
        "Recent and historical acceptance records should be merged"
    )

    assert_equal(
        submissions_metadata[
            "historical_files_loaded"
        ],
        1,
        "Historical acceptance shard should load"
    )

    assert_equal(
        submissions_metadata[
            "historical_files_failed"
        ],
        0,
        "Synthetic historical acceptance load should be complete"
    )

    def selection_fact(metric, value, start, end, filed, accession,
                       concept=None, unit="USD", namespace="us-gaap"):
        concepts = {
            "revenue": "RevenueFromContractWithCustomerExcludingAssessedTax",
            "net_income": "NetIncomeLoss",
        }
        return {
            "metric": metric,
            "namespace": namespace,
            "concept": concept or concepts[metric],
            "unit": unit,
            "value": value,
            "start": start,
            "end": end,
            "filed": filed,
            "available_date": str(
                date.fromisoformat(filed) + timedelta(days=1)
            ),
            "form": "10-Q",
            "fiscal_year": 2021,
            "fiscal_period": "Q2",
            "accession": accession,
            "accepted_at": None,
            "frame": None,
        }

    selection_record = {
        "ticker": "SELECT",
        "facts": [
            selection_fact("revenue", 100, "2021-01-01", "2021-03-31",
                           "2021-05-01", "q1-original"),
            selection_fact("revenue", 200, "2021-04-01", "2021-06-30",
                           "2021-08-01", "q2"),
            selection_fact("revenue", 300, "2021-01-01", "2021-06-30",
                           "2021-08-01", "q2-ytd"),
            selection_fact("revenue", 110, "2021-01-01", "2021-03-31",
                           "2021-09-01", "q1-late-amendment"),
            selection_fact("net_income", 25, "2021-04-01", "2021-06-30",
                           "2021-08-01", "net-filing"),
            selection_fact("net_income", 30, "2021-04-01", "2021-06-30",
                           "2021-08-01", "net-filing", concept="ProfitLoss"),
        ],
    }
    comparable_quarter = build_snapshot_as_of(selection_record, "2021-09-02")
    assert_equal(
        comparable_quarter["metrics"]["revenue"]["value"], 200,
        "A late amendment to an older period must not displace the latest period",
    )
    assert_equal(
        comparable_quarter["metrics"]["net_income"]["value"], 25,
        "Canonical concept priority must resolve overlapping mapped concepts",
    )
    assert_equal(
        comparable_quarter["duration_context_aligned"], True,
        "Selected quarter contexts should be exactly aligned",
    )
    ytd_snapshot = build_snapshot_as_of(
        selection_record, "2021-09-02", duration_period="year_to_date"
    )
    assert_equal(
        ytd_snapshot["metrics"]["revenue"]["value"], 300,
        "Quarter and year-to-date values must remain separate",
    )

    multi_currency_record = {
        "ticker": "CURRENCY",
        "facts": [
            selection_fact("revenue", 100, "2021-01-01", "2021-12-31",
                           "2022-02-01", "annual-filing", unit="USD"),
            selection_fact("revenue", 650, "2021-01-01", "2021-12-31",
                           "2022-02-01", "annual-filing", unit="CNY"),
        ],
    }
    ambiguous_currency = build_snapshot_as_of(
        multi_currency_record, "2022-02-02", duration_period="annual"
    )
    assert_equal(
        ambiguous_currency["selection_issues"]["revenue"],
        "ambiguous_reporting_currency",
        "Multiple reported currencies must fail closed without a requested currency",
    )
    cny_snapshot = build_snapshot_as_of(
        multi_currency_record, "2022-02-02",
        duration_period="annual", currency="CNY"
    )
    assert_equal(
        cny_snapshot["metrics"]["revenue"]["value"], 650,
        "An explicit reported currency may be selected without FX conversion",
    )
    assert_equal(
        cny_snapshot["currency_conversion_applied"], False,
        "Snapshot selection must never imply an FX conversion",
    )
    assert_equal(
        cny_snapshot["research_use_authorized"], False,
        "Comparable data selection must not authorize research use",
    )

    quality_summary = build_quality_summary([
        {
            **record,
            "status":
            "COMPLETE",
            "submissions_metadata":
            submissions_metadata
        },
        {
            "ticker":
            "MISSING",
            "status":
            "CIK_NOT_FOUND",
            "fact_count":
            0,
            "submissions_metadata": {
                "status":
                None
            }
        }
    ])

    assert_equal(
        quality_summary[
            "ticker_count"
        ],
        2,
        "Quality summary should retain the requested universe denominator"
    )

    assert_equal(
        quality_summary[
            "fact_ticker_coverage_pct"
        ],
        50.0,
        "Fact coverage should include missing-CIK securities in denominator"
    )

    assert_equal(
        quality_summary[
            "submissions_status_counts"
        ][
            "NOT_AVAILABLE"
        ],
        1,
        "Missing submissions metadata should be counted explicitly"
    )

    print(
        json.dumps({
            "status":
            "PASS",

            "tests": [
                "original_before_amendment",
                "amendment_only_after_available_date",
                "acceptance_timestamp_preserved",
                "ifrs_revenue_normalized",
                "metric_and_taxonomy_coverage_measured",
                "historical_acceptance_shards_loaded",
                "pre_xbrl_and_unsafe_shards_rejected",
                "archive_quality_summary_measured",
                "latest_period_precedes_late_amendment",
                "quarter_and_ytd_separated",
                "canonical_concept_priority_applied",
                "ambiguous_currency_fails_closed",
                "no_fx_conversion_or_research_authorization"
            ]
        },
        indent=2)
    )


if __name__ == "__main__":
    main()
