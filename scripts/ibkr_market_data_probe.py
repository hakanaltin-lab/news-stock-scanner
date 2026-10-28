"""AURORA V8.9.7 G3 IBKR real-time market-data probe.

Usage:
    python scripts/ibkr_market_data_probe.py NVDA

This probe never submits an order. Exit code 0 means the quote is verified
real-time and passes the execution market-data quality gate.
"""

import json
import os
from pathlib import Path
import sys
import tempfile

from engines.ibkr_market_data_connector import (
    get_ibkr_realtime_quote,
)
from engines.market_data_quality_gate import (
    evaluate_market_data_for_execution,
)


DEFAULT_OUTPUT = (
    "runtime/ibkr_market_data/latest.json"
)


def _write_atomic(path, payload):
    target = Path(path)
    target.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=str(target.parent),
        delete=False,
    ) as handle:
        json.dump(
            payload,
            handle,
            indent=2,
            sort_keys=True,
        )
        handle.write("\n")
        temp_name = handle.name

    os.replace(
        temp_name,
        target,
    )


def main():
    symbol = (
        sys.argv[1].strip().upper()
        if len(sys.argv) > 1
        else ""
    )

    snapshot = get_ibkr_realtime_quote(symbol)

    quote = snapshot.get(
        "quote",
        {},
    ) or {}

    execution_gate = (
        evaluate_market_data_for_execution(
            quote
        )
        if quote
        else {
            "execution_eligible": False,
            "decision": "BLOCK",
            "failure_reasons": [
                "NO_QUOTE_AVAILABLE"
            ],
        }
    )

    proof = {
        "engine": (
            "AURORA V8.9.7 G3 "
            "IBKR Market Data Probe"
        ),
        "symbol": symbol or None,
        "snapshot": snapshot,
        "execution_market_data_gate": execution_gate,
        "broker_submission_allowed": False,
        "paper_order_submission_allowed": False,
        "live_execution_allowed": False,
    }

    output = os.getenv(
        "AURORA_IBKR_MARKET_DATA_PROBE_OUTPUT",
        DEFAULT_OUTPUT,
    )

    _write_atomic(
        output,
        proof,
    )

    print(json.dumps(
        {
            "symbol": proof["symbol"],
            "snapshot_status": snapshot.get(
                "status"
            ),
            "market_data_type": quote.get(
                "market_data_type_name"
            ),
            "execution_gate": execution_gate.get(
                "decision"
            ),
            "execution_eligible": execution_gate.get(
                "execution_eligible"
            ),
            "broker_submission_allowed": False,
            "output": output,
        },
        indent=2,
        sort_keys=True,
    ))

    return (
        0
        if (
            snapshot.get("status")
            == "REALTIME_READY"
            and execution_gate.get(
                "execution_eligible"
            )
            is True
        )
        else 2
    )


if __name__ == "__main__":
    raise SystemExit(main())
