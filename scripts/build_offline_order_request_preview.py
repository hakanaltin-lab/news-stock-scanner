#!/usr/bin/env python3
"""Build a G8.22 offline order-request preview from a bounded intent file."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import stat
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from engines.gateway_readonly_attestation_verifier import (
    _load_json_bytes,
    _repository_is_clean,
)
from engines.offline_order_request_materializer import (
    materialize_offline_order_request,
)
from scripts.gateway_review_package import (
    read_trusted_runtime_evidence_json,
)
from scripts.ibkr_paper_probe import (
    write_runtime_evidence_atomic,
)


DEFAULT_DESIGN_PATH = (
    REPOSITORY_ROOT
    / "config/offline_order_request_materializer_design_v1.json"
)
DEFAULT_CANDIDATE_ATTESTATION = (
    REPOSITORY_ROOT
    / "runtime/aurora_g6_candidate_attestation/latest.json"
)
DEFAULT_OUTPUT = (
    REPOSITORY_ROOT
    / "runtime/aurora_g6_offline_order_request/latest.json"
)
MAX_INTENT_BYTES = 16384


def _blocked(reason):
    return {
        "engine": "AURORA G8.22 Offline Order Request CLI",
        "status": "BLOCKED",
        "reason": reason,
        "offline_request_materialized": False,
        "candidate_attestation_verified": False,
        "request": None,
        "broker_request_materialized": False,
        "broker_order_object_created": False,
        "network_accessed": False,
        "transmit": False,
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
        "next_gate": "REPAIR_OFFLINE_ORDER_REQUEST_INPUT",
    }


def _read_intent(path):
    target = Path(path)
    try:
        metadata = target.lstat()
    except OSError:
        return None

    if (
        stat.S_ISLNK(metadata.st_mode)
        or not stat.S_ISREG(metadata.st_mode)
        or metadata.st_size <= 0
        or metadata.st_size > MAX_INTENT_BYTES
    ):
        return None

    try:
        raw = target.read_bytes()
        if len(raw) != metadata.st_size:
            return None
        value = _load_json_bytes(raw)
    except (
        OSError,
        UnicodeDecodeError,
        ValueError,
        TypeError,
    ):
        return None

    return value if isinstance(value, dict) else None


def build_installed_offline_request(intent_path):
    clean_before = _repository_is_clean(
        REPOSITORY_ROOT
    )
    if clean_before is not True:
        return _blocked("REPOSITORY_NOT_CLEAN")

    try:
        design = _load_json_bytes(
            DEFAULT_DESIGN_PATH.read_bytes()
        )
    except (
        OSError,
        UnicodeDecodeError,
        ValueError,
        TypeError,
    ):
        return _blocked(
            "MATERIALIZER_DESIGN_PARSE_FAILED"
        )

    attestation = read_trusted_runtime_evidence_json(
        DEFAULT_CANDIDATE_ATTESTATION
    )
    intent = _read_intent(
        intent_path
    )

    clean_after = _repository_is_clean(
        REPOSITORY_ROOT
    )
    if (
        not attestation
        or intent is None
        or clean_after is not True
    ):
        return _blocked(
            "OFFLINE_MATERIALIZER_INPUT_UNTRUSTED"
        )

    return materialize_offline_order_request(
        design,
        attestation,
        intent,
    )


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--intent-file",
        required=True,
    )
    args = parser.parse_args(argv)

    result = build_installed_offline_request(
        args.intent_file
    )

    try:
        write_runtime_evidence_atomic(
            DEFAULT_OUTPUT,
            result,
        )
    except (
        OSError,
        RuntimeError,
        ValueError,
    ):
        result = _blocked(
            "OFFLINE_ORDER_REQUEST_WRITE_FAILED"
        )

    print(
        json.dumps(
            result,
            indent=2,
            sort_keys=True,
        )
    )

    return (
        0
        if result.get(
            "offline_request_materialized"
        )
        is True
        else 2
    )


if __name__ == "__main__":
    raise SystemExit(main())
