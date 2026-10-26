import json

from engines.sec_edgar_point_in_time_engine import (
    build_snapshot_as_of,
    normalize_companyfacts
)


def assert_equal(
    actual,
    expected,
    message
):
    if actual != expected:
        raise AssertionError(
            f"{message}: expected={expected!r} actual={actual!r}"
        )


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
        "2020-02-16"
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

    print(
        json.dumps({
            "status":
            "PASS",

            "tests": [
                "original_before_amendment",
                "amendment_only_after_available_date",
                "acceptance_timestamp_preserved",
                "ifrs_revenue_normalized"
            ]
        },
        indent=2)
    )


if __name__ == "__main__":
    main()
