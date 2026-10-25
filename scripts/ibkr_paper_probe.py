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

    print(
        json.dumps(
            {
                "snapshot":
                snapshot,

                "readiness":
                readiness
            },
            indent=2
        )
    )


if __name__ == "__main__":
    main()
