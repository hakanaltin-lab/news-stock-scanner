#!/usr/bin/env python3
"""Render a non-attesting Gateway Read-Only reviewer handoff preflight."""

import json
from pathlib import Path
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from engines.gateway_attestation_handoff import (
    build_installed_reviewer_handoff,
)


def main():
    result = build_installed_reviewer_handoff(
        REPOSITORY_ROOT
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
        if result.get("status")
        == "READY_FOR_INDEPENDENT_REVIEW"
        else 2
    )


if __name__ == "__main__":
    raise SystemExit(main())
