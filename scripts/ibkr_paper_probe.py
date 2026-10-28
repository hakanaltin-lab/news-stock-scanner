"""
Standalone V8.9.4 IBKR Paper Read-Only Probe

Run this on the VPS where IB Gateway is running after the official IBKR
TWS Python API has been installed.

No orders are submitted. A non-zero exit code is returned unless every
required read-only readiness check passes.
"""

import csv
import json
import os
from pathlib import Path
import sys


REPOSITORY_ROOT = Path(
    __file__
).resolve().parents[1]

# Support both documented entry points:
#   python scripts/ibkr_paper_probe.py
#   python -m scripts.ibkr_paper_probe
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(
        0,
        str(REPOSITORY_ROOT)
    )

from engines.ibkr_gateway_connector import (
    get_ibkr_read_only_snapshot
)

from engines.ibkr_paper_readiness_engine import (
    evaluate_ibkr_paper_readiness
)


PORTFOLIO_FILE = Path(
    os.getenv(
        "AURORA_IBKR_PORTFOLIO_FILE",
        str(
            REPOSITORY_ROOT
            /
            "data/portfolio.csv"
        )
    )
).expanduser()

RUNTIME_OUTPUT_FILE = Path(
    os.getenv(
        "AURORA_IBKR_PROBE_OUTPUT",
        str(
            REPOSITORY_ROOT
            /
            "runtime/ibkr_paper_read_only/latest.json"
        )
    )
).expanduser()


def load_portfolio():
    rows = []

    if not PORTFOLIO_FILE.exists():
        return rows

    with PORTFOLIO_FILE.open(
        mode="r",
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

    RUNTIME_OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    temporary_output = (
        RUNTIME_OUTPUT_FILE.with_suffix(
            RUNTIME_OUTPUT_FILE.suffix
            +
            ".tmp"
        )
    )

    temporary_output.write_text(
        json.dumps(
            result,
            indent=2
        )
        +
        "\n",
        encoding="utf-8"
    )

    temporary_output.replace(
        RUNTIME_OUTPUT_FILE
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
                str(
                    RUNTIME_OUTPUT_FILE
                ),

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

    if (
        readiness.get(
            "readiness"
        )
        ==
        "READY_FOR_PAPER_READ_ONLY"
    ):
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
