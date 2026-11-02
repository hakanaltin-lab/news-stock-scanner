"""
Standalone V8.9.5 IBKR Paper Read-Only Probe

Run this on the VPS where IB Gateway is running after the official IBKR
TWS Python API has been installed.

No orders are submitted. A non-zero exit code is returned unless every
required read-only readiness check passes.
"""

import csv
import hashlib
import json
import os
from pathlib import Path
import subprocess
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

from engines.gce_runtime_identity import (
    EXPECTED_INSTANCE_NAME,
    EXPECTED_PROJECT_ID,
    EXPECTED_ZONE,
    read_gce_runtime_identity,
)

from engines.gateway_readonly_attestation_verifier import (
    verify_installed_gateway_readonly_attestation
)

from engines.ibkr_paper_readiness_engine import (
    evaluate_ibkr_paper_readiness
)


from engines.aurora_run_mode_engine import (
    load_run_mode
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

G0_RUNTIME_PROOF_FILE = (
    REPOSITORY_ROOT
    /
    "runtime/gcp/latest.json"
)

_REQUIRED_G0_CHECKS = {
    "source_payloads_valid",
    "budget_guard_passed",
    "vm_identity",
    "vm_instance_id_valid",
    "vm_running",
    "vm_hardened",
    "network_contract",
    "iap_ssh_only_rule",
    "public_private_ports_denied",
    "no_public_allow_for_sensitive_ports",
}

_PERMISSION_FLAGS = (
    "broker_submission_allowed",
    "paper_order_submission_allowed",
    "live_execution_allowed",
    "automatic_promotion_allowed",
)


class DuplicateJsonKeyError(ValueError):
    pass


def _reject_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateJsonKeyError(
                f"duplicate JSON key: {key}"
            )
        result[key] = value
    return result


def _canonical_sha256(payload):
    encoded = json.dumps(
        payload or {},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def load_g0_runtime_proof():
    try:
        raw = G0_RUNTIME_PROOF_FILE.read_text(
            encoding="utf-8"
        )
        value = json.loads(
            raw,
            object_pairs_hook=_reject_duplicate_keys,
        )
    except (
        OSError,
        UnicodeDecodeError,
        json.JSONDecodeError,
        DuplicateJsonKeyError,
    ):
        return {}

    return value if isinstance(value, dict) else {}


def build_runtime_provenance(
    runtime_cloud_identity,
    g0_proof,
):
    identity = (
        runtime_cloud_identity
        if isinstance(runtime_cloud_identity, dict)
        else {}
    )
    g0 = (
        g0_proof
        if isinstance(g0_proof, dict)
        else {}
    )

    instance_id = identity.get("instance_id")
    identity_verified = (
        identity.get("status") == "VERIFIED"
        and identity.get("verified") is True
        and identity.get("failure_reasons") == []
        and identity.get("project_id") == EXPECTED_PROJECT_ID
        and identity.get("instance_name") == EXPECTED_INSTANCE_NAME
        and identity.get("zone") == EXPECTED_ZONE
        and isinstance(instance_id, str)
        and instance_id.isdigit()
        and 6 <= len(instance_id) <= 30
        and instance_id[0] != "0"
    )

    g0_checks = (
        g0.get("checks")
        if isinstance(g0.get("checks"), dict)
        else {}
    )
    g0_verified = (
        g0.get("engine")
        == "AURORA V8.9.20 G0-G1 Runtime Proof"
        and g0.get("status") == "G0_G1_VERIFIED"
        and g0.get("failure_reasons") == []
        and g0.get("project_id") == EXPECTED_PROJECT_ID
        and g0.get("vm_name") == EXPECTED_INSTANCE_NAME
        and g0.get("zone") == EXPECTED_ZONE
        and identity_verified
        and g0.get("gce_instance_id") == instance_id
        and _REQUIRED_G0_CHECKS.issubset(g0_checks)
        and all(
            g0_checks.get(name) is True
            for name in _REQUIRED_G0_CHECKS
        )
        and all(
            g0.get(name) is False
            for name in _PERMISSION_FLAGS
        )
    )

    failures = []
    if not identity_verified:
        failures.append(
            "GCE_RUNTIME_IDENTITY_UNVERIFIED"
        )
    if not g0_verified:
        failures.append(
            "G0_RUNTIME_PROOF_UNVERIFIED"
        )

    verified = not failures

    return {
        "verified": verified,
        "runtime_cloud_identity": (
            {
                "project_id": identity.get("project_id"),
                "instance_name": identity.get("instance_name"),
                "zone": identity.get("zone"),
                "instance_id": identity.get("instance_id"),
            }
            if identity_verified
            else None
        ),
        "g0_runtime_proof_sha256": (
            _canonical_sha256(g0)
            if g0_verified
            else None
        ),
        "failure_reasons": failures,
        "broker_submission_allowed": False,
        "paper_order_submission_allowed": False,
        "live_execution_allowed": False,
        "automatic_promotion_allowed": False,
        "real_money_trading_allowed": False,
    }


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


def _current_git_sha():
    try:
        completed = subprocess.run(
            [
                "/usr/bin/git",
                "-C",
                str(REPOSITORY_ROOT),
                "rev-parse",
                "HEAD",
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
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

    value = completed.stdout.strip().lower()
    if (
        completed.returncode != 0
        or len(value) != 40
        or any(
            character not in "0123456789abcdef"
            for character in value
        )
    ):
        return None

    return value


def main():
    run_mode = load_run_mode()

    runtime_provenance = build_runtime_provenance(
        read_gce_runtime_identity(),
        load_g0_runtime_proof(),
    )

    snapshot = (
        get_ibkr_read_only_snapshot()
    )

    gateway_attestation = (
        verify_installed_gateway_readonly_attestation(
            REPOSITORY_ROOT
        )
    )

    snapshot[
        "gateway_read_only_configuration_independently_attested"
    ] = (
        gateway_attestation.get(
            "gateway_read_only_configuration_independently_attested"
        )
        is True
    )

    readiness = (
        evaluate_ibkr_paper_readiness(
            snapshot,
            load_portfolio()
        )
    )

    result = {
        "git_sha":
        _current_git_sha(),

        "evidence_run_id":
        os.getenv(
            "AURORA_EVIDENCE_RUN_ID",
            ""
        ).strip() or None,

        "run_mode":
        run_mode,

        "runtime_provenance":
        runtime_provenance,

        "snapshot":
        snapshot,

        "gateway_read_only_attestation":
        gateway_attestation,

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
                "run_mode":
                run_mode.get(
                    "mode"
                ),

                "runtime_provenance_verified":
                runtime_provenance.get(
                    "verified"
                ),

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

                "gateway_attestation_status":
                gateway_attestation.get(
                    "status"
                ),

                "gateway_read_only_configuration_independently_attested":
                gateway_attestation.get(
                    "gateway_read_only_configuration_independently_attested"
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
