"""
Standalone V8.3 IBKR Paper Read-Only Probe

Run this on the VPS where IB Gateway is running after the official IBKR
TWS Python API has been installed.

No orders are submitted.
"""

import csv
import json
import os

from engines.ibkr_gateway_connector import (
    get_ibkr_read_only_snapshot
)

from engines.ibkr_paper_readiness_engine import (
    evaluate_ibkr_paper_readiness
)


PORTFOLIO_FILE = "data/portfolio.csv"
RUNTIME_OUTPUT_FILE = "runtime/ibkr_paper_read_only/latest.json"


def load_portfolio():
    rows = []

    if not os.path.exists(
        PORTFOLIO_FILE
    ):
        return rows

    with open(
        PORTFOLIO_FILE,
        "r",
        encoding="utf-8"
    ) as file:
        reader = csv.DictReader(
            file
        )

        rows.extend(
            reader
        )

    return rows


def main():
    snapshot = (
        get_ibkr_read_only_snapshot()
    )

    readiness = (
        evaluate_ibkr_paper_readiness(
            snapshot,
            load_portfolio()
        )
    )

    result = {
        "snapshot":
        snapshot,

        "readiness":
        readiness
    }

    os.makedirs(
        os.path.dirname(
            RUNTIME_OUTPUT_FILE
        ),
        exist_ok=True
    )

    with open(
        RUNTIME_OUTPUT_FILE,
        "w",
        encoding="utf-8"
    ) as file:
        json.dump(
            result,
            file,
            indent=2
        )

    print(
        json.dumps(
            {
                "snapshot_status":
                snapshot.get(
                    "status"
                ),

                "connection_status":
                snapshot.get(
                    "connection_status"
                ),

                "readiness":
                readiness.get(
                    "readiness"
                ),

                "required_failure_count":
                readiness.get(
                    "required_failure_count"
                ),

                "runtime_output":
                RUNTIME_OUTPUT_FILE,

                "paper_order_submission_allowed":
                readiness.get(
                    "paper_order_submission_allowed"
                ),

                "live_execution_allowed":
                readiness.get(
                    "live_execution_allowed"
                )
            },
            indent=2
        )
    )


if __name__ == "__main__":
    main()
