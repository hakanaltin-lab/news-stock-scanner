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
import stat
import subprocess
import sys
import tempfile


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

from scripts.gateway_review_workflow_status import (
    build_installed_gateway_review_workflow_status,
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

MAX_RUNTIME_EVIDENCE_BYTES = 1024 * 1024
RUNTIME_EVIDENCE_MODE = 0o600


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


def _runtime_evidence_bytes(payload):
    encoded = (
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
        )
        +
        "\n"
    ).encode("utf-8")

    if (
        not encoded
        or len(encoded) > MAX_RUNTIME_EVIDENCE_BYTES
    ):
        raise ValueError(
            "runtime evidence size invalid"
        )

    return encoded


def write_runtime_evidence_atomic(
    path,
    payload,
):
    target = Path(path)
    target.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    if target.parent.is_symlink():
        raise RuntimeError(
            "runtime evidence parent symlink forbidden"
        )

    try:
        existing = target.lstat()
    except FileNotFoundError:
        existing = None

    if existing is not None:
        if (
            stat.S_ISLNK(existing.st_mode)
            or not stat.S_ISREG(existing.st_mode)
        ):
            raise RuntimeError(
                "runtime evidence target type invalid"
            )

    encoded = _runtime_evidence_bytes(
        payload
    )

    temporary_name = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=str(target.parent),
            prefix=".aurora-g2-",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary_name = handle.name
            os.fchmod(
                handle.fileno(),
                RUNTIME_EVIDENCE_MODE,
            )
            handle.write(encoded)
            handle.flush()
            os.fsync(
                handle.fileno()
            )
            temporary_stat = os.fstat(
                handle.fileno()
            )

        os.replace(
            temporary_name,
            target,
        )
        temporary_name = None

        final_stat = target.lstat()
        if (
            not stat.S_ISREG(final_stat.st_mode)
            or stat.S_IMODE(final_stat.st_mode)
            != RUNTIME_EVIDENCE_MODE
            or final_stat.st_nlink != 1
            or final_stat.st_dev != temporary_stat.st_dev
            or final_stat.st_ino != temporary_stat.st_ino
        ):
            raise RuntimeError(
                "runtime evidence final file unsafe"
            )

        directory_flags = (
            os.O_RDONLY
            |
            getattr(
                os,
                "O_DIRECTORY",
                0,
            )
        )
        directory_fd = os.open(
            target.parent,
            directory_flags,
        )
        try:
            os.fsync(
                directory_fd
            )
        finally:
            os.close(
                directory_fd
            )

    finally:
        if temporary_name is not None:
            try:
                Path(
                    temporary_name
                ).unlink()
            except FileNotFoundError:
                pass


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


def _preconnection_stage(run_mode, runtime_provenance, review):
    """Return the only broker-read stages allowed before opening an IBKR socket."""
    required_flags = (
        "broker_submission_allowed",
        "paper_order_submission_allowed",
        "live_execution_allowed",
        "automatic_promotion_allowed",
        "real_money_trading_allowed",
    )
    common_safe = (
        isinstance(run_mode, dict)
        and run_mode.get("mode") == "READ_ONLY"
        and run_mode.get("mode_valid") is True
        and run_mode.get("read_only") is True
        and run_mode.get("paper_order_submission_requested") is False
        and run_mode.get("live_execution_allowed") is False
        and isinstance(runtime_provenance, dict)
        and runtime_provenance.get("verified") is True
        and isinstance(review, dict)
        and review.get("runtime_identity_verified") is True
        and review.get("handoff_ready") is True
        and all(
            review.get(flag) is False
            for flag in required_flags
        )
    )
    if not common_safe:
        return None

    pre_review_diagnostic = (
        review.get("status") == "BLOCKED"
        and review.get("workflow_stage") == "REVIEW_PACKAGE"
        and review.get("next_action") == "RUN_FRESH_G2_DIAGNOSTIC_PRE_REVIEW"
        and review.get("human_action_required") is True
        and review.get("review_package_ready") is False
        and review.get("signed_attestation_verified") is False
        and review.get("failure_reasons")
        == ["G2_DIAGNOSTIC_REVIEW_PACKAGE_NOT_READY"]
    )
    if pre_review_diagnostic:
        return "PRE_REVIEW_DIAGNOSTIC"

    post_review_probe = (
        review.get("status") == "VERIFIED_FOR_G2_READ_ONLY_PROBE"
        and review.get("workflow_stage") == "SIGNED_ATTESTATION_VERIFIED"
        and review.get("next_action") == "RUN_G2_PAPER_READ_ONLY_PROBE"
        and review.get("human_action_required") is False
        and review.get("signed_attestation_verified") is True
        and review.get("failure_reasons") == []
    )
    if post_review_probe:
        return "POST_REVIEW_PROBE"

    return None


def _preconnection_gate(run_mode, runtime_provenance, review):
    return _preconnection_stage(
        run_mode,
        runtime_provenance,
        review,
    ) is not None


def main():
    run_mode = load_run_mode()

    runtime_provenance = build_runtime_provenance(
        read_gce_runtime_identity(),
        load_g0_runtime_proof(),
    )
    try:
        review = build_installed_gateway_review_workflow_status()
    except (OSError, RuntimeError, ValueError, TypeError, KeyError):
        review = {}

    probe_stage = _preconnection_stage(
        run_mode,
        runtime_provenance,
        review,
    )
    if probe_stage is None:
        print(json.dumps({
            "status": "BLOCKED_BEFORE_BROKER_CONNECTION",
            "reason": "G6_EXTERNAL_READ_ONLY_ACCEPTANCE_REQUIRED",
            "paper_order_submission_allowed": False,
            "live_execution_allowed": False,
        }, sort_keys=True))
        return 2

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
        "probe_stage":
        probe_stage,

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

    try:
        write_runtime_evidence_atomic(
            RUNTIME_OUTPUT_FILE,
            result,
        )
    except (
        OSError,
        RuntimeError,
        ValueError,
    ):
        print(
            json.dumps(
                {
                    "status":
                    "RUNTIME_EVIDENCE_WRITE_FAILED",

                    "runtime_output":
                    str(
                        RUNTIME_OUTPUT_FILE
                    ),

                    "paper_order_submission_allowed":
                    False,

                    "live_execution_allowed":
                    False,
                },
                indent=2,
            )
        )
        return 2

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
