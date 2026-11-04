#!/usr/bin/env python3
"""Build sanitized unsigned Gateway Read-Only review packages.

The legacy V1 builder validates only the trusted reviewer handoff. The G8.3
runtime-bound V3 builder additionally requires a fresh, sanitized IBKR Paper
diagnostic proof from the fixed G2 runtime path and binds it to the same live
GCE instance plus the same G0/G1 control-plane proof used by the handoff.

Neither builder signs evidence, creates a positive attestation, nor enables any
broker execution permission.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
from uuid import UUID

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from engines.gateway_attestation_handoff import (
    HANDOFF_REQUEST_TYPE,
    build_installed_reviewer_handoff,
)
from engines.gateway_readonly_attestation_verifier import (
    ATTESTATION_TYPE,
    SIGNATURE_ALGORITHM,
)


PACKAGE_TYPE = "IBKR_GATEWAY_READ_ONLY_REVIEW_PACKAGE_V1"
RUNTIME_BOUND_PACKAGE_TYPE = "IBKR_GATEWAY_READ_ONLY_REVIEW_PACKAGE_V3"
RUNTIME_BOUND_PACKAGE_SCHEMA_VERSION = 3
DEFAULT_G2_DIAGNOSTIC_PROOF = (
    REPOSITORY_ROOT
    / "runtime/ibkr_paper_read_only/latest.json"
)
DEFAULT_MAX_G2_DIAGNOSTIC_AGE_SECONDS = 300
MAX_G2_DIAGNOSTIC_PROOF_BYTES = 1024 * 1024
TRUSTED_G2_EVIDENCE_MODE = 0o600

_PERMISSION_FLAGS = (
    "broker_submission_allowed",
    "paper_order_submission_allowed",
    "live_execution_allowed",
    "automatic_promotion_allowed",
    "real_money_trading_allowed",
)

_REQUIRED_MUTATION_METHODS = {
    "placeOrder",
    "cancelOrder",
    "reqGlobalCancel",
    "exerciseOptions",
    "replaceFA",
    "reqAutoOpenOrders",
}

_REQUIRED_G2_PASSED_CHECKS = {
    "paper_mode_only",
    "safe_loopback_paper_endpoint",
    "paper_account_allowlist_configured",
    "paper_account_identity_verified",
    "verified_account_fingerprint_payload_valid",
    "account_summary_accounts_match_managed_accounts",
    "connector_read_only",
    "order_submission_hard_blocked",
    "broker_mutation_surface_hard_blocked",
    "nonbinding_open_order_observation",
    "nonzero_api_client_id",
    "live_trading_hard_blocked",
    "official_ibapi_available",
    "gateway_connected",
    "managed_account_identity_consistent",
    "managed_account_received",
    "single_managed_account_for_readiness",
    "net_liquidation_available",
    "cash_available",
    "available_funds_available",
    "managed_accounts_snapshot_complete",
    "account_summary_snapshot_complete",
    "positions_snapshot_complete",
    "open_orders_snapshot_complete",
    "open_orders_payload_valid",
    "open_order_identifiers_unique",
    "open_order_statuses_active",
    "open_order_execution_evidence_consistent",
    "open_order_accounts_match_verified_paper_accounts",
    "positions_payload_valid",
    "position_accounts_match_verified_paper_accounts",
    "portfolio_quantities_and_symbols_valid",
    "position_instruments_unambiguous",
}

_ATTESTATION_CHECK = (
    "gateway_read_only_configuration_independently_attested"
)

_HANDOFF_REQUEST_FIELDS = {
    "request_schema_version",
    "request_type",
    "requested_control",
    "generated_at_utc",
    "git_sha",
    "instance_name",
    "zone",
    "broker_mode",
    "gateway_port",
    "reviewer_id",
    "reviewer_public_key_sha256",
    "gcp_project_id",
    "gcp_instance_id",
    "reviewer_policy_sha256",
    "g0_runtime_proof_sha256",
    "g0_runtime_proof_generated_at",
    "g0_runtime_project_id",
    "g0_runtime_zone",
    "g0_runtime_vm_name",
    "g0_runtime_instance_id",
    "operator_asserts_gateway_read_only",
    "requires_human_gateway_configuration_review",
    "signed_attestation_required",
    "broker_submission_allowed",
    "paper_order_submission_allowed",
    "live_execution_allowed",
    "automatic_promotion_allowed",
    "real_money_trading_allowed",
}


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
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _blocked(
    reason,
    *,
    package_type=PACKAGE_TYPE,
    package_schema_version=1,
):
    return {
        "package_type": package_type,
        "package_schema_version": package_schema_version,
        "status": "BLOCKED",
        "ready_for_independent_review": False,
        "attestation_verified": False,
        "gateway_read_only_configuration_independently_attested": False,
        "failure_reasons": [reason],
        "handoff_request_sha256": None,
        "handoff_request": None,
        "g2_diagnostic_proof_sha256": None,
        "g2_diagnostic_summary": None,
        "unsigned_artifact_template": None,
        "broker_submission_allowed": False,
        "paper_order_submission_allowed": False,
        "live_execution_allowed": False,
        "automatic_promotion_allowed": False,
        "real_money_trading_allowed": False,
    }


def build_unsigned_review_package(handoff_result):
    """Legacy V1 handoff-only builder kept for offline compatibility tests."""

    if not isinstance(handoff_result, dict):
        return _blocked("HANDOFF_RESULT_INVALID")

    request = handoff_result.get("handoff_request")
    safe_handoff = (
        handoff_result.get("status") == "READY_FOR_INDEPENDENT_REVIEW"
        and handoff_result.get("ready_for_independent_review") is True
        and handoff_result.get("attestation_verified") is False
        and handoff_result.get(
            "gateway_read_only_configuration_independently_attested"
        ) is False
        and isinstance(request, dict)
        and set(request) == _HANDOFF_REQUEST_FIELDS
        and request.get("request_schema_version") == 3
        and request.get("request_type") == HANDOFF_REQUEST_TYPE
        and request.get("requested_control") == ATTESTATION_TYPE
        and request.get("operator_asserts_gateway_read_only") is False
        and request.get(
            "requires_human_gateway_configuration_review"
        ) is True
        and request.get("signed_attestation_required") is True
        and all(
            handoff_result.get(name) is False
            for name in _PERMISSION_FLAGS
        )
        and all(
            request.get(name) is False
            for name in _PERMISSION_FLAGS
        )
    )
    if not safe_handoff:
        return _blocked(
            "HANDOFF_RESULT_NOT_SAFE_FOR_REVIEW_PACKAGE"
        )

    template = {
        "schema_version": 3,
        "attestation_id": None,
        "attestation_type": ATTESTATION_TYPE,
        "decision": "REVIEW_REQUIRED",
        "reviewer_id": request.get("reviewer_id"),
        "captured_at_utc": None,
        "expires_at_utc": None,
        "git_sha": request.get("git_sha"),
        "instance_name": request.get("instance_name"),
        "zone": request.get("zone"),
        "gcp_project_id": request.get("gcp_project_id"),
        "gcp_instance_id": request.get("gcp_instance_id"),
        "broker_mode": request.get("broker_mode"),
        "gateway_port": request.get("gateway_port"),
        "read_only_api_enabled": None,
        "evidence_sha256": None,
        "g0_runtime_proof_sha256": request.get(
            "g0_runtime_proof_sha256"
        ),
        "signature_algorithm": SIGNATURE_ALGORITHM,
        "signature_b64": None,
    }

    return {
        "package_type": PACKAGE_TYPE,
        "package_schema_version": 1,
        "status": "READY_FOR_INDEPENDENT_REVIEW_PACKAGE",
        "ready_for_independent_review": True,
        "attestation_verified": False,
        "gateway_read_only_configuration_independently_attested": False,
        "failure_reasons": [],
        "handoff_request_sha256": _canonical_sha256(request),
        "handoff_request": request,
        "g2_diagnostic_proof_sha256": None,
        "g2_diagnostic_summary": None,
        "unsigned_artifact_template": template,
        "reviewer_must_set": [
            "attestation_id",
            "decision=ATTESTED only after independent review",
            "captured_at_utc",
            "expires_at_utc",
            "read_only_api_enabled=true only after independent review",
            "evidence_sha256",
            "signature_b64",
        ],
        "broker_submission_allowed": False,
        "paper_order_submission_allowed": False,
        "live_execution_allowed": False,
        "automatic_promotion_allowed": False,
        "real_money_trading_allowed": False,
    }


def _utc_datetime(value):
    text = str(value or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def _uuid4(value):
    text = str(value or "").strip()
    try:
        parsed = UUID(text)
    except (ValueError, AttributeError):
        return None
    if parsed.version != 4 or str(parsed) != text:
        return None
    return text


def _fingerprints(value):
    if not isinstance(value, list) or not value:
        return ()
    normalized = tuple(str(item).strip() for item in value)
    if tuple(sorted(set(normalized))) != normalized:
        return ()
    if any(
        len(item) != 15
        or not item.startswith("IBKR-")
        or any(
            character not in "0123456789ABCDEF"
            for character in item[5:]
        )
        for item in normalized
    ):
        return ()
    return normalized


def _accounts_in_rows_are_verified(rows, fingerprints):
    return (
        isinstance(rows, list)
        and all(
            isinstance(row, dict)
            and isinstance(row.get("account"), str)
            and row.get("account") in fingerprints
            for row in rows
        )
    )


def _safe_attestation_absent(attestation):
    return (
        isinstance(attestation, dict)
        and attestation.get("status") != "VERIFIED"
        and attestation.get("verified") is False
        and attestation.get(
            "gateway_read_only_configuration_independently_attested"
        ) is False
        and all(
            attestation.get(name) is False
            for name in _PERMISSION_FLAGS
        )
    )


def _validate_g2_diagnostic(
    g2_proof,
    handoff_request,
    *,
    now,
    max_age_seconds,
):
    if not isinstance(g2_proof, dict):
        return None, "G2_DIAGNOSTIC_PROOF_INVALID"

    if (
        type(max_age_seconds) is not int
        or not 30 <= max_age_seconds <= 900
    ):
        return None, "G2_DIAGNOSTIC_MAX_AGE_INVALID"

    evidence_run_id = _uuid4(
        g2_proof.get("evidence_run_id")
    )
    if evidence_run_id is None:
        return None, "G2_DIAGNOSTIC_EVIDENCE_RUN_ID_INVALID"

    if g2_proof.get("probe_stage") != "PRE_REVIEW_DIAGNOSTIC":
        return None, "G2_DIAGNOSTIC_PROBE_STAGE_INVALID"

    git_sha = str(g2_proof.get("git_sha") or "").strip().lower()
    handoff_git_sha = str(
        handoff_request.get("git_sha") or ""
    ).strip().lower()
    if (
        len(git_sha) != 40
        or any(character not in "0123456789abcdef" for character in git_sha)
        or git_sha != handoff_git_sha
    ):
        return None, "G2_DIAGNOSTIC_GIT_SHA_NOT_BOUND"

    provenance = g2_proof.get("runtime_provenance")
    if not isinstance(provenance, dict):
        return None, "G2_DIAGNOSTIC_RUNTIME_PROVENANCE_INVALID"

    provenance_identity = provenance.get(
        "runtime_cloud_identity"
    )
    if not isinstance(provenance_identity, dict):
        return None, "G2_DIAGNOSTIC_GCE_IDENTITY_NOT_BOUND"

    handoff_instance_id = str(
        handoff_request.get("gcp_instance_id") or ""
    ).strip()
    provenance_identity_safe = (
        provenance.get("verified") is True
        and provenance.get("failure_reasons") == []
        and provenance_identity.get("project_id")
        == handoff_request.get("gcp_project_id")
        and provenance_identity.get("instance_name")
        == handoff_request.get("instance_name")
        and provenance_identity.get("zone")
        == handoff_request.get("zone")
        and provenance_identity.get("instance_id")
        == handoff_instance_id
        and handoff_instance_id.isdigit()
        and 6 <= len(handoff_instance_id) <= 30
        and handoff_instance_id[0] != "0"
        and all(
            provenance.get(name) is False
            for name in _PERMISSION_FLAGS
        )
    )
    if not provenance_identity_safe:
        return None, "G2_DIAGNOSTIC_GCE_IDENTITY_NOT_BOUND"

    provenance_g0_sha256 = str(
        provenance.get("g0_runtime_proof_sha256") or ""
    ).strip().lower()
    handoff_g0_sha256 = str(
        handoff_request.get("g0_runtime_proof_sha256") or ""
    ).strip().lower()
    provenance_g0_safe = (
        len(provenance_g0_sha256) == 64
        and all(
            character in "0123456789abcdef"
            for character in provenance_g0_sha256
        )
        and provenance_g0_sha256 == handoff_g0_sha256
    )
    if not provenance_g0_safe:
        return None, "G2_DIAGNOSTIC_G0_PROOF_NOT_BOUND"

    run_mode = g2_proof.get("run_mode")
    snapshot = g2_proof.get("snapshot")
    readiness = g2_proof.get("readiness")
    attestation = g2_proof.get("gateway_read_only_attestation")
    if not all(
        isinstance(value, dict)
        for value in (
            run_mode,
            snapshot,
            readiness,
            attestation,
        )
    ):
        return None, "G2_DIAGNOSTIC_STRUCTURE_INVALID"

    if (
        run_mode.get("mode") != "READ_ONLY"
        or run_mode.get("live_execution_allowed") is not False
    ):
        return None, "G2_DIAGNOSTIC_RUN_MODE_UNSAFE"

    config = snapshot.get("config")
    if not isinstance(config, dict):
        return None, "G2_DIAGNOSTIC_CONFIG_INVALID"

    client_id = config.get("client_id")
    mutation_methods = snapshot.get(
        "blocked_broker_mutation_methods"
    )
    mutation_methods_safe = (
        isinstance(mutation_methods, list)
        and len(mutation_methods) == len(
            _REQUIRED_MUTATION_METHODS
        )
        and all(
            isinstance(method, str)
            for method in mutation_methods
        )
        and set(mutation_methods)
        == _REQUIRED_MUTATION_METHODS
    )
    config_safe = (
        snapshot.get("status") == "CONNECTED"
        and snapshot.get("connection_status") == "CONNECTED"
        and snapshot.get("official_ibapi_available") is True
        and config.get("enabled") is True
        and config.get("mode") == "PAPER"
        and config.get("mode_valid") is True
        and config.get("host") == "127.0.0.1"
        and config.get("port") == 4002
        and config.get("port_valid") is True
        and config.get("endpoint_safe") is True
        and config.get("read_only") is True
        and type(client_id) is int
        and client_id > 0
        and config.get("client_id_valid") is True
        and snapshot.get("order_submission_hard_blocked") is True
        and snapshot.get("broker_mutation_surface_hard_blocked") is True
        and snapshot.get("client_zero_binding_hard_blocked") is True
        and snapshot.get("open_order_observation_mode")
        == "REQ_ALL_OPEN_ORDERS_NON_BINDING"
        and mutation_methods_safe
        and snapshot.get("live_trading_allowed") is False
    )
    if not config_safe:
        return None, "G2_DIAGNOSTIC_CONNECTOR_SAFETY_INVALID"

    account_guard = snapshot.get("paper_account_guard")
    if not isinstance(account_guard, dict):
        return None, "G2_DIAGNOSTIC_ACCOUNT_GUARD_INVALID"

    fingerprints = _fingerprints(
        account_guard.get("verified_account_fingerprints")
    )
    snapshot_fingerprints = _fingerprints(
        snapshot.get("accounts")
    )
    summary_fingerprints = _fingerprints(
        snapshot.get("account_summary_account_fingerprints")
    )
    account_safe = (
        bool(fingerprints)
        and len(fingerprints) == 1
        and snapshot_fingerprints == fingerprints
        and summary_fingerprints == fingerprints
        and account_guard.get("allowlist_configured") is True
        and account_guard.get("paper_account_verified") is True
        and account_guard.get("account_count") == 1
        and snapshot.get("account_count") == 1
        and _accounts_in_rows_are_verified(
            snapshot.get("positions"),
            fingerprints,
        )
        and _accounts_in_rows_are_verified(
            snapshot.get("open_orders"),
            fingerprints,
        )
    )
    if not account_safe:
        return None, "G2_DIAGNOSTIC_ACCOUNT_IDENTITY_INVALID"

    requests_complete = snapshot.get("requests_complete")
    if (
        not isinstance(requests_complete, dict)
        or any(
            requests_complete.get(name) is not True
            for name in (
                "managed_accounts",
                "account_summary",
                "positions",
                "open_orders",
            )
        )
    ):
        return None, "G2_DIAGNOSTIC_REQUESTS_INCOMPLETE"

    if not _safe_attestation_absent(attestation):
        return None, "G2_DIAGNOSTIC_PRE_REVIEW_ATTESTATION_STATE_INVALID"

    if (
        snapshot.get(
            "gateway_read_only_configuration_independently_attested"
        ) is not False
        or readiness.get(
            "gateway_read_only_configuration_independently_attested"
        ) is not False
        or readiness.get("readiness") != "NOT_READY"
        or readiness.get("diagnostic_read_only_ready") is not True
        or readiness.get("next_milestone")
        != "INDEPENDENT_GATEWAY_READ_ONLY_ATTESTATION"
        or readiness.get("paper_order_submission_allowed") is not False
        or readiness.get("live_execution_allowed") is not False
    ):
        return None, "G2_DIAGNOSTIC_READINESS_STATE_INVALID"

    checks = readiness.get("checks")
    if (
        not isinstance(checks, list)
        or not checks
        or not all(
            isinstance(item, dict)
            and isinstance(item.get("check"), str)
            and type(item.get("required")) is bool
            and type(item.get("passed")) is bool
            for item in checks
        )
    ):
        return None, "G2_DIAGNOSTIC_CHECKS_INVALID"

    check_names = [item["check"] for item in checks]
    if len(check_names) != len(set(check_names)):
        return None, "G2_DIAGNOSTIC_CHECKS_DUPLICATED"

    required_failures = {
        item["check"]
        for item in checks
        if item["required"] is True
        and item["passed"] is False
    }
    passed_required = {
        item["check"]
        for item in checks
        if item["required"] is True
        and item["passed"] is True
    }
    if (
        required_failures != {_ATTESTATION_CHECK}
        or readiness.get("required_failure_count") != 1
        or not _REQUIRED_G2_PASSED_CHECKS.issubset(
            passed_required
        )
    ):
        return None, "G2_DIAGNOSTIC_REQUIRED_CHECKS_NOT_CLEAN"

    captured_at = _utc_datetime(
        readiness.get("timestamp")
        or snapshot.get("timestamp")
    )
    if captured_at is None:
        return None, "G2_DIAGNOSTIC_TIMESTAMP_INVALID"

    age_seconds = (now - captured_at).total_seconds()
    if age_seconds < -2 or age_seconds > max_age_seconds:
        return None, "G2_DIAGNOSTIC_NOT_FRESH"

    summary = {
        "evidence_run_id": evidence_run_id,
        "probe_stage": "PRE_REVIEW_DIAGNOSTIC",
        "captured_at_utc": captured_at.isoformat(),
        "age_seconds": round(max(0.0, age_seconds), 3),
        "git_sha": git_sha,
        "gcp_project_id": provenance_identity.get(
            "project_id"
        ),
        "gcp_instance_id": provenance_identity.get(
            "instance_id"
        ),
        "g0_runtime_proof_sha256": provenance_g0_sha256,
        "snapshot_status": snapshot.get("status"),
        "connection_status": snapshot.get("connection_status"),
        "broker_mode": config.get("mode"),
        "gateway_host": config.get("host"),
        "gateway_port": config.get("port"),
        "api_client_id": client_id,
        "paper_account_fingerprints": list(fingerprints),
        "diagnostic_read_only_ready": True,
        "only_required_failure": _ATTESTATION_CHECK,
        "broker_mutation_surface_hard_blocked": True,
        "open_order_observation_mode": (
            "REQ_ALL_OPEN_ORDERS_NON_BINDING"
        ),
        "client_zero_binding_hard_blocked": True,
    }
    return summary, None


def build_runtime_bound_review_package(
    handoff_result,
    g2_proof,
    *,
    now=None,
    max_age_seconds=DEFAULT_MAX_G2_DIAGNOSTIC_AGE_SECONDS,
):
    """Build V3 only from a safe handoff plus deployment-bound G2 evidence."""

    v1 = build_unsigned_review_package(
        handoff_result
    )
    if (
        v1.get("status")
        != "READY_FOR_INDEPENDENT_REVIEW_PACKAGE"
    ):
        return _blocked(
            "HANDOFF_RESULT_NOT_SAFE_FOR_RUNTIME_BOUND_PACKAGE",
            package_type=RUNTIME_BOUND_PACKAGE_TYPE,
            package_schema_version=RUNTIME_BOUND_PACKAGE_SCHEMA_VERSION,
        )

    request = v1["handoff_request"]
    current_time = (
        now.astimezone(timezone.utc)
        if isinstance(now, datetime)
        and now.tzinfo is not None
        else datetime.now(timezone.utc)
    )
    summary, failure = _validate_g2_diagnostic(
        g2_proof,
        request,
        now=current_time,
        max_age_seconds=max_age_seconds,
    )
    if failure:
        return _blocked(
            failure,
            package_type=RUNTIME_BOUND_PACKAGE_TYPE,
            package_schema_version=2,
        )

    return {
        **v1,
        "package_type": RUNTIME_BOUND_PACKAGE_TYPE,
        "package_schema_version": RUNTIME_BOUND_PACKAGE_SCHEMA_VERSION,
        "g2_diagnostic_proof_sha256": _canonical_sha256(
            g2_proof
        ),
        "g2_diagnostic_summary": summary,
    }


def _read_trusted_runtime_evidence_bytes(path):
    """Read one owner-only regular file without following symlinks."""

    nofollow = getattr(
        os,
        "O_NOFOLLOW",
        0,
    )
    if not nofollow:
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
            Path(path),
            flags,
        )
    except OSError:
        return None

    try:
        before = os.fstat(
            descriptor
        )
        mode = stat.S_IMODE(
            before.st_mode
        )

        trusted = (
            stat.S_ISREG(before.st_mode)
            and before.st_uid == os.geteuid()
            and before.st_nlink == 1
            and mode == TRUSTED_G2_EVIDENCE_MODE
            and 0 < before.st_size
            <= MAX_G2_DIAGNOSTIC_PROOF_BYTES
        )
        if not trusted:
            return None

        chunks = []
        remaining = (
            MAX_G2_DIAGNOSTIC_PROOF_BYTES
            + 1
        )

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
            and stat.S_IMODE(after.st_mode)
            == TRUSTED_G2_EVIDENCE_MODE
            and len(raw) == before.st_size
            and len(raw)
            <= MAX_G2_DIAGNOSTIC_PROOF_BYTES
        )
        if not stable:
            return None

        return raw

    except OSError:
        return None

    finally:
        os.close(
            descriptor
        )


def read_trusted_runtime_evidence_json(path):
    """Read one owner-only trusted runtime JSON object."""

    raw = _read_trusted_runtime_evidence_bytes(
        path
    )
    if raw is None:
        return {}

    try:
        value = json.loads(
            raw.decode(
                "utf-8",
                errors="strict",
            ),
            object_pairs_hook=_reject_duplicate_keys,
        )
    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
        DuplicateJsonKeyError,
    ):
        return {}

    return value if isinstance(value, dict) else {}


def load_installed_g2_diagnostic_proof():
    """Read only the fixed owner-only deployed G2 diagnostic path."""

    return read_trusted_runtime_evidence_json(
        DEFAULT_G2_DIAGNOSTIC_PROOF
    )


def main():
    handoff = build_installed_reviewer_handoff(
        REPOSITORY_ROOT
    )
    result = build_runtime_bound_review_package(
        handoff,
        load_installed_g2_diagnostic_proof(),
    )
    print(
        json.dumps(
            result,
            sort_keys=True,
        )
    )
    return (
        0
        if result["status"]
        == "READY_FOR_INDEPENDENT_REVIEW_PACKAGE"
        else 2
    )


if __name__ == "__main__":
    raise SystemExit(main())
