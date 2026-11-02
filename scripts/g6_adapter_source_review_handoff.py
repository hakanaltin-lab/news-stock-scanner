#!/usr/bin/env python3
"""Build the trusted G8.14 independent adapter source-review handoff package."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from engines.gateway_readonly_attestation_verifier import (
    _current_git_sha,
    _repository_is_clean,
)
from engines.paper_adapter_source_handoff import (
    evaluate_source_review_handoff,
)
from scripts.g6_adapter_source_review import (
    _read_fixed_tracked_source,
)
from scripts.gateway_review_package import (
    read_trusted_runtime_evidence_json,
)
from scripts.ibkr_paper_probe import (
    write_runtime_evidence_atomic,
)


DEFAULT_SOURCE_REVIEW = (
    "runtime/aurora_g6_source_review/latest.json"
)
DEFAULT_OUTPUT = (
    "runtime/aurora_g6_source_review_handoff/latest.json"
)


def _blocked(reason):
    return {
        "engine": "AURORA G8.14 Adapter Source Review Handoff CLI",
        "status": "BLOCKED",
        "reason": reason,
        "ready_for_independent_source_review": False,
        "source_policy_revalidated": False,
        "source_attestation_verified": False,
        "operator_asserts_source_safe": False,
        "review_request": None,
        "unsigned_attestation_template": None,
        "independent_source_review_required": True,
        "signed_source_attestation_required": True,
        "implementation_allowed": False,
        "connection_allowed": False,
        "broker_request_materialization_allowed": False,
        "broker_order_object_allowed": False,
        "automatic_retry_allowed": False,
        "automatic_cancel_allowed": False,
        "automatic_modify_allowed": False,
        "broker_submission_allowed": False,
        "paper_order_submission_allowed": False,
        "live_execution_allowed": False,
        "automatic_promotion_allowed": False,
        "real_money_trading_allowed": False,
        "next_gate": "REPAIR_ADAPTER_SOURCE_REVIEW_HANDOFF",
    }


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source-review",
        default=DEFAULT_SOURCE_REVIEW,
    )
    parser.add_argument(
        "--output",
        default=DEFAULT_OUTPUT,
    )
    args = parser.parse_args(argv)

    current_git_sha = _current_git_sha(
        REPOSITORY_ROOT
    )
    clean_before = _repository_is_clean(
        REPOSITORY_ROOT
    )
    source_text = _read_fixed_tracked_source()
    clean_after = _repository_is_clean(
        REPOSITORY_ROOT
    )

    if (
        current_git_sha is None
        or clean_before is not True
        or clean_after is not True
        or source_text is None
    ):
        result = _blocked(
            "TRACKED_SOURCE_OR_REPOSITORY_STATE_UNTRUSTED"
        )
    else:
        result = evaluate_source_review_handoff(
            read_trusted_runtime_evidence_json(
                args.source_review
            ),
            source_text,
            current_git_sha,
            True,
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
        print(
            json.dumps(
                _blocked(
                    "SOURCE_REVIEW_HANDOFF_WRITE_FAILED"
                ),
                indent=2,
                sort_keys=True,
            )
        )
        return 2

    print(
        json.dumps(
            result,
            indent=2,
            sort_keys=True,
        )
    )

    return (
        0
        if result.get("status")
        == "READY_FOR_INDEPENDENT_ADAPTER_SOURCE_REVIEW"
        else 2
    )


if __name__ == "__main__":
    raise SystemExit(main())
