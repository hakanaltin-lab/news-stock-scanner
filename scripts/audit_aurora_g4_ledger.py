#!/usr/bin/env python3
"""Write a sanitized, read-only G4 shadow-ledger audit report."""

import argparse
import json
import os
from pathlib import Path
import sys
import tempfile


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from engines.shadow_audit_verifier import verify_shadow_ledger


DEFAULT_LEDGER = "runtime/aurora_g4_shadow/shadow_audit.sqlite3"
DEFAULT_OUTPUT = "runtime/aurora_g4_shadow/ledger_audit.json"
DEFAULT_G4_SHADOW = "runtime/aurora_g4_shadow/latest.json"


def _read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _write_atomic(path, payload):
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=str(target.parent),
        delete=False,
    ) as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
        temporary = handle.name
    os.replace(temporary, target)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--ledger", default=DEFAULT_LEDGER)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument("--g4-shadow", default=DEFAULT_G4_SHADOW)
    args = parser.parse_args(argv)

    g4_shadow = _read_json(args.g4_shadow)
    result = verify_shadow_ledger(
        args.ledger,
        expected_receipt=g4_shadow.get("ledger_receipt"),
    )
    _write_atomic(args.output, result)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("status") == "LEDGER_VERIFIED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
