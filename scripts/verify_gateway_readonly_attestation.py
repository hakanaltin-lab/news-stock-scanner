#!/usr/bin/env python3
"""Print the fixed-path Gateway Read-Only attestation verification result."""

import json
from pathlib import Path
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from engines.gateway_readonly_attestation_verifier import (
    verify_installed_gateway_readonly_attestation,
)


def main():
    result = verify_installed_gateway_readonly_attestation(
        REPOSITORY_ROOT
    )
    print(
        json.dumps(
            result,
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if result.get("verified") is True else 2


if __name__ == "__main__":
    raise SystemExit(main())
