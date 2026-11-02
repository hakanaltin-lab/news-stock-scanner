#!/usr/bin/env python3
"""Build the trusted G8.13 non-executable Paper adapter source-review artifact."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import stat
import subprocess
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from engines.gateway_readonly_attestation_verifier import (
    _current_git_sha,
    _repository_is_clean,
)
from engines.paper_adapter_source_review import (
    evaluate_adapter_source_review,
)
from scripts.gateway_review_package import (
    read_trusted_runtime_evidence_json,
)
from scripts.ibkr_paper_probe import (
    write_runtime_evidence_atomic,
)


DEFAULT_PREREQUISITE = (
    "runtime/aurora_g6_runtime_prerequisite/latest.json"
)
DEFAULT_OUTPUT = (
    "runtime/aurora_g6_source_review/latest.json"
)
SOURCE_RELATIVE_PATH = (
    "broker_engine/ibkr_paper_adapter_review_skeleton.py"
)
MAX_SOURCE_BYTES = 100_000


def _blocked(reason):
    return {
        "engine": "AURORA G8.13 Paper Adapter Source Review CLI",
        "status": "BLOCKED",
        "reason": reason,
        "source_policy_validated": False,
        "independent_source_review_required": True,
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
        "next_gate": "REPAIR_ADAPTER_SOURCE_REVIEW_INPUT",
    }


def _read_fixed_tracked_source():
    path = (
        REPOSITORY_ROOT
        / SOURCE_RELATIVE_PATH
    )

    nofollow = getattr(
        os,
        "O_NOFOLLOW",
        0,
    )
    if not nofollow:
        return None

    try:
        link_info = path.lstat()
    except OSError:
        return None

    if (
        stat.S_ISLNK(link_info.st_mode)
        or not stat.S_ISREG(link_info.st_mode)
        or link_info.st_uid != os.geteuid()
        or link_info.st_nlink != 1
        or link_info.st_mode & 0o022
        or not 0 < link_info.st_size <= MAX_SOURCE_BYTES
    ):
        return None

    flags = (
        os.O_RDONLY
        |
        nofollow
        |
        getattr(
            os,
            "O_CLOEXEC",
            0,
        )
    )

    try:
        descriptor = os.open(
            path,
            flags,
        )
    except OSError:
        return None

    try:
        before = os.fstat(
            descriptor
        )
        chunks = []
        remaining = MAX_SOURCE_BYTES + 1

        while remaining > 0:
            chunk = os.read(
                descriptor,
                min(
                    65536,
                    remaining,
                ),
            )
            if not chunk:
                break
            chunks.append(
                chunk
            )
            remaining -= len(
                chunk
            )

        raw = b"".join(
            chunks
        )
        after = os.fstat(
            descriptor
        )

        stable = (
            before.st_dev == after.st_dev
            and before.st_ino == after.st_ino
            and before.st_size == after.st_size
            and before.st_mtime_ns == after.st_mtime_ns
            and before.st_ctime_ns == after.st_ctime_ns
            and after.st_nlink == 1
            and len(raw) == before.st_size
            and len(raw) <= MAX_SOURCE_BYTES
        )
        if not stable:
            return None
    except OSError:
        return None
    finally:
        os.close(
            descriptor
        )

    try:
        completed = subprocess.run(
            [
                "/usr/bin/git",
                "-C",
                str(REPOSITORY_ROOT),
                "show",
                f"HEAD:{SOURCE_RELATIVE_PATH}",
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=3,
            env={
                "PATH": "/usr/bin:/bin",
                "LANG": "C",
                "LC_ALL": "C",
            },
        )
    except (
        OSError,
        subprocess.SubprocessError,
    ):
        return None

    if (
        completed.returncode != 0
        or completed.stdout != raw
    ):
        return None

    try:
        return raw.decode(
            "utf-8",
            errors="strict",
        )
    except UnicodeDecodeError:
        return None


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--prerequisite",
        default=DEFAULT_PREREQUISITE,
    )
    parser.add_argument(
        "--output",
        default=DEFAULT_OUTPUT,
    )
    args = parser.parse_args(argv)

    current_git_sha = _current_git_sha(
        REPOSITORY_ROOT
    )
    repository_clean_before = (
        _repository_is_clean(
            REPOSITORY_ROOT
        )
    )
    source_text = _read_fixed_tracked_source()
    repository_clean_after = (
        _repository_is_clean(
            REPOSITORY_ROOT
        )
    )

    if (
        current_git_sha is None
        or repository_clean_before is not True
        or repository_clean_after is not True
        or source_text is None
    ):
        result = _blocked(
            "TRACKED_SOURCE_OR_REPOSITORY_STATE_UNTRUSTED"
        )
    else:
        result = evaluate_adapter_source_review(
            read_trusted_runtime_evidence_json(
                args.prerequisite
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
                    "SOURCE_REVIEW_ARTIFACT_WRITE_FAILED"
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
        == "SOURCE_POLICY_VALIDATED_NON_EXECUTABLE"
        else 2
    )


if __name__ == "__main__":
    raise SystemExit(main())
