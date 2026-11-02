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


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from engines.ibkr_market_data_connector import (
    get_ibkr_realtime_quote,
)
from engines.market_data_quality_gate import (
    evaluate_market_data_for_execution,
)
from engines.gce_runtime_identity import (
    read_gce_runtime_identity,
)
from scripts.ibkr_paper_probe import (
    _current_git_sha,
    build_runtime_provenance,
    load_g0_runtime_proof,
    write_runtime_evidence_atomic,
)


DEFAULT_OUTPUT = (
    "runtime/ibkr_market_data/latest.json"
)


def main():
    symbol = (
        sys.argv[1].strip().upper()
        if len(sys.argv) > 1
        else ""
    )

    runtime_provenance = build_runtime_provenance(
        read_gce_runtime_identity(),
        load_g0_runtime_proof(),
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
        "git_sha": _current_git_sha(),
        "evidence_run_id": os.getenv(
            "AURORA_EVIDENCE_RUN_ID",
            "",
        ).strip() or None,
        "runtime_provenance": runtime_provenance,
        "symbol": symbol or None,
        "snapshot": snapshot,
        "execution_market_data_gate": execution_gate,
        "broker_submission_allowed": False,
        "paper_order_submission_allowed": False,
        "live_execution_allowed": False,
        "automatic_promotion_allowed": False,
        "real_money_trading_allowed": False,
    }

    output = os.getenv(
        "AURORA_IBKR_MARKET_DATA_PROBE_OUTPUT",
        DEFAULT_OUTPUT,
    )

    try:
        write_runtime_evidence_atomic(
            output,
            proof,
        )
    except (
        OSError,
        RuntimeError,
        ValueError,
    ):
        print(json.dumps(
            {
                "status": "RUNTIME_EVIDENCE_WRITE_FAILED",
                "runtime_provenance_verified": (
                    runtime_provenance.get("verified")
                ),
                "broker_submission_allowed": False,
                "paper_order_submission_allowed": False,
                "live_execution_allowed": False,
                "output": output,
            },
            indent=2,
            sort_keys=True,
        ))
        return 2

    print(json.dumps(
        {
            "symbol": proof["symbol"],
            "runtime_provenance_verified": (
                runtime_provenance.get("verified")
            ),
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
            runtime_provenance.get("verified")
            is True
            and snapshot.get("status")
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
