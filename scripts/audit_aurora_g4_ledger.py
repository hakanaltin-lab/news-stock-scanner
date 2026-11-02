#!/usr/bin/env python3
"""Write a sanitized, read-only G4 shadow-ledger audit report."""

import argparse
import json
from pathlib import Path
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from engines.shadow_audit_verifier import verify_shadow_ledger
from scripts.gateway_review_package import (
    read_trusted_runtime_evidence_json,
)
from scripts.ibkr_paper_probe import (
    write_runtime_evidence_atomic,
)


DEFAULT_LEDGER = "runtime/aurora_g4_shadow/shadow_audit.sqlite3"
DEFAULT_OUTPUT = "runtime/aurora_g4_shadow/ledger_audit.json"
DEFAULT_G4_SHADOW = "runtime/aurora_g4_shadow/latest.json"


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--ledger", default=DEFAULT_LEDGER)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument("--g4-shadow", default=DEFAULT_G4_SHADOW)
    args = parser.parse_args(argv)

    g4_shadow = read_trusted_runtime_evidence_json(
        args.g4_shadow
    )
    result = verify_shadow_ledger(
        args.ledger,
        expected_receipt=g4_shadow.get("ledger_receipt"),
    )
    try:
        write_runtime_evidence_atomic(
            args.output,
            result,
        )
    except (
        OSError,
        RuntimeError,
        ValueError,
    ):
        print(json.dumps({
            "status": "RUNTIME_EVIDENCE_WRITE_FAILED",
            "broker_submission_allowed": False,
            "paper_order_submission_allowed": False,
            "live_execution_allowed": False,
            "automatic_promotion_allowed": False,
            "real_money_trading_allowed": False,
        }, indent=2, sort_keys=True))
        return 2

    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("status") == "LEDGER_VERIFIED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
