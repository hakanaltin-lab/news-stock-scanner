"""Fail-closed operator/reviewer handoff preflight for Gateway Read-Only review.

This module never creates a positive Gateway/TWS Read-Only attestation and never
signs evidence.  It only proves that the reviewer trust root and the deployed
repository are ready for an independent human review.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import socket

from engines.gce_runtime_identity import (
    read_gce_runtime_identity,
)

from engines.gateway_readonly_attestation_verifier import (
    ATTESTATION_TYPE,
    DEFAULT_POLICY_PATH,
    DEFAULT_PUBLIC_KEY_PATH,
    OPENSSL_BIN,
    _current_git_sha,
    _load_json_bytes,
    _repository_is_clean,
    _trusted_root_file,
)


ENGINE_VERSION = "AURORA G7.6 Gateway Read-Only Reviewer Handoff Preflight"
HANDOFF_REQUEST_TYPE = "IBKR_GATEWAY_READ_ONLY_REVIEW_REQUEST_V1"
EXPECTED_INSTANCE_NAME = "aurora-trading-vps"
EXPECTED_ZONE = "europe-west3-a"
EXPECTED_PROJECT_ID = "project-ce9773ef-6814-469c-92b"
DEFAULT_G0_PROOF_RELATIVE_PATH = Path("runtime/gcp/latest.json")
MAX_G0_PROOF_AGE_SECONDS = 86400

_POLICY_FIELDS = {
    "policy_version",
    "reviewer_id",
    "public_key_sha256",
    "expected_instance_name",
    "expected_zone",
    "expected_project_id",
    "expected_instance_id",
    "max_attestation_age_seconds",
    "allowed_clock_skew_seconds",
}

_HEX_40 = re.compile(r"^[0-9a-f]{40}$")
_HEX_64 = re.compile(r"^[0-9a-f]{64}$")
_REVIEWER_ID = re.compile(r"^[A-Za-z0-9._@+-]{3,128}$")


def _canonical_sha256(payload):
    encoded = json.dumps(
        payload or {},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(
        encoded
    ).hexdigest()


def _blocked(reason):
    return {
        "engine": ENGINE_VERSION,
        "status": "BLOCKED",
        "ready_for_independent_review": False,
        "attestation_verified": False,
        "gateway_read_only_configuration_independently_attested": False,
        "failure_reasons": [reason],
        "handoff_request": None,
        "broker_submission_allowed": False,
        "paper_order_submission_allowed": False,
        "live_execution_allowed": False,
        "automatic_promotion_allowed": False,
        "real_money_trading_allowed": False,
    }


def evaluate_reviewer_handoff_preflight(
    policy,
    public_key_bytes,
    current_git_sha,
    current_instance_name,
    repository_clean,
    openssl_available,
    g0_proof,
    runtime_cloud_identity,
    now=None,
):
    """Evaluate whether the VPS is ready to hand off to an independent reviewer."""

    now = (
        now.astimezone(timezone.utc)
        if isinstance(now, datetime)
        and now.tzinfo is not None
        else datetime.now(timezone.utc)
    )

    failures = []

    def require(name, condition):
        if not condition:
            failures.append(name)

    policy_is_dict = isinstance(policy, dict)
    require("policy_is_object", policy_is_dict)

    if not policy_is_dict:
        policy = {}

    require(
        "policy_field_set_exact",
        set(policy) == _POLICY_FIELDS,
    )
    require(
        "policy_version",
        type(policy.get("policy_version")) is int
        and policy.get("policy_version") == 2,
    )

    reviewer_id = policy.get("reviewer_id")
    require(
        "reviewer_id_format",
        isinstance(reviewer_id, str)
        and bool(_REVIEWER_ID.fullmatch(reviewer_id)),
    )

    policy_key_sha256 = str(
        policy.get("public_key_sha256") or ""
    ).strip().lower()
    require(
        "policy_public_key_sha256_valid",
        bool(_HEX_64.fullmatch(policy_key_sha256))
        and policy_key_sha256 != ("0" * 64),
    )

    public_key_material_valid = (
        isinstance(public_key_bytes, bytes)
        and b"-----BEGIN PUBLIC KEY-----" in public_key_bytes
        and b"PRIVATE KEY" not in public_key_bytes
    )
    require(
        "reviewer_public_key_material_valid",
        public_key_material_valid,
    )

    public_key_sha256 = (
        hashlib.sha256(public_key_bytes).hexdigest()
        if isinstance(public_key_bytes, bytes)
        else ""
    )
    require(
        "public_key_matches_policy",
        bool(public_key_sha256)
        and public_key_sha256 == policy_key_sha256,
    )

    expected_instance_name = policy.get("expected_instance_name")
    expected_zone = policy.get("expected_zone")

    require(
        "approved_instance_policy",
        expected_instance_name == EXPECTED_INSTANCE_NAME,
    )
    require(
        "runtime_instance_matches_policy",
        str(current_instance_name or "").strip()
        == expected_instance_name,
    )
    require(
        "approved_zone_policy",
        expected_zone == EXPECTED_ZONE,
    )

    project_value = policy.get(
        "expected_project_id"
    )
    instance_id_value = policy.get(
        "expected_instance_id"
    )
    expected_project_id = (
        project_value.strip()
        if isinstance(
            project_value,
            str,
        )
        else ""
    )
    expected_instance_id = (
        instance_id_value.strip()
        if isinstance(
            instance_id_value,
            str,
        )
        else ""
    )

    require(
        "approved_project_policy",
        isinstance(
            project_value,
            str,
        )
        and expected_project_id == EXPECTED_PROJECT_ID,
    )
    require(
        "expected_instance_id_valid",
        isinstance(
            instance_id_value,
            str,
        )
        and expected_instance_id.isdigit()
        and 6 <= len(expected_instance_id) <= 30
        and expected_instance_id[0] != "0",
    )

    runtime_cloud_identity = (
        runtime_cloud_identity
        if isinstance(
            runtime_cloud_identity,
            dict,
        )
        else {}
    )
    require(
        "gce_runtime_identity_verified",
        runtime_cloud_identity.get("status") == "VERIFIED"
        and runtime_cloud_identity.get("verified") is True,
    )
    require(
        "gce_runtime_project_bound",
        runtime_cloud_identity.get("project_id")
        == expected_project_id,
    )
    require(
        "gce_runtime_instance_name_bound",
        runtime_cloud_identity.get("instance_name")
        == expected_instance_name,
    )
    require(
        "gce_runtime_zone_bound",
        runtime_cloud_identity.get("zone")
        == expected_zone,
    )
    require(
        "gce_runtime_instance_id_bound",
        runtime_cloud_identity.get("instance_id")
        == expected_instance_id,
    )

    current_git_sha = str(
        current_git_sha or ""
    ).strip().lower()
    require(
        "current_git_sha_valid",
        bool(_HEX_40.fullmatch(current_git_sha)),
    )
    require(
        "repository_clean",
        repository_clean is True,
    )
    require(
        "openssl_available",
        openssl_available is True,
    )

    g0_is_dict = isinstance(g0_proof, dict)
    require(
        "g0_proof_is_object",
        g0_is_dict,
    )
    if not g0_is_dict:
        g0_proof = {}

    g0_generated_at = str(
        g0_proof.get("generated_at") or ""
    ).strip()
    g0_timestamp = None
    if g0_generated_at:
        text = g0_generated_at
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(text)
            if parsed.tzinfo is not None:
                g0_timestamp = parsed.astimezone(
                    timezone.utc
                )
        except ValueError:
            g0_timestamp = None

    g0_age_seconds = (
        (now - g0_timestamp).total_seconds()
        if g0_timestamp is not None
        else None
    )

    g0_checks = (
        g0_proof.get("checks")
        if isinstance(
            g0_proof.get("checks"),
            dict,
        )
        else {}
    )
    required_g0_checks = (
        "budget_guard_passed",
        "vm_identity",
        "vm_running",
        "vm_hardened",
        "network_contract",
        "iap_ssh_only_rule",
        "public_private_ports_denied",
        "no_public_allow_for_sensitive_ports",
    )

    require(
        "g0_runtime_verified",
        g0_proof.get("engine")
        == "AURORA V8.9.20 G0-G1 Runtime Proof"
        and g0_proof.get("status") == "G0_G1_VERIFIED"
        and isinstance(
            g0_proof.get("failure_reasons"),
            list,
        )
        and g0_proof.get("failure_reasons") == []
        and isinstance(
            g0_proof.get("public_sensitive_allow_rules"),
            list,
        )
        and g0_proof.get("public_sensitive_allow_rules") == [],
    )
    require(
        "g0_runtime_identity_bound",
        g0_proof.get("project_id") == EXPECTED_PROJECT_ID
        and g0_proof.get("zone") == EXPECTED_ZONE
        and g0_proof.get("vm_name") == EXPECTED_INSTANCE_NAME,
    )
    require(
        "g0_runtime_checks_complete",
        bool(g0_checks)
        and all(
            g0_checks.get(name) is True
            for name in required_g0_checks
        ),
    )
    require(
        "g0_runtime_proof_fresh",
        g0_age_seconds is not None
        and -2
        <= g0_age_seconds
        <= MAX_G0_PROOF_AGE_SECONDS,
    )
    require(
        "g0_order_permissions_blocked",
        all(
            g0_proof.get(name) is False
            for name in (
                "broker_submission_allowed",
                "paper_order_submission_allowed",
                "live_execution_allowed",
                "automatic_promotion_allowed",
            )
        ),
    )

    max_age = policy.get("max_attestation_age_seconds")
    clock_skew = policy.get("allowed_clock_skew_seconds")
    require(
        "policy_max_age_valid",
        type(max_age) is int
        and 60 <= max_age <= 86400,
    )
    require(
        "policy_clock_skew_valid",
        type(clock_skew) is int
        and 0 <= clock_skew <= 300,
    )

    ready = not failures

    handoff_request = None
    if ready:
        handoff_request = {
            "request_schema_version": 1,
            "request_type": HANDOFF_REQUEST_TYPE,
            "requested_control": ATTESTATION_TYPE,
            "generated_at_utc": now.isoformat(),
            "git_sha": current_git_sha,
            "instance_name": expected_instance_name,
            "zone": expected_zone,
            "broker_mode": "PAPER",
            "gateway_port": 4002,
            "reviewer_id": reviewer_id,
            "reviewer_public_key_sha256": public_key_sha256,
            "gcp_project_id": expected_project_id,
            "gcp_instance_id": expected_instance_id,
            "reviewer_policy_sha256": _canonical_sha256(
                policy
            ),
            "g0_runtime_proof_sha256": _canonical_sha256(
                g0_proof
            ),
            "g0_runtime_proof_generated_at": g0_proof.get("generated_at"),
            "g0_runtime_project_id": g0_proof.get("project_id"),
            "g0_runtime_zone": g0_proof.get("zone"),
            "g0_runtime_vm_name": g0_proof.get("vm_name"),
            "operator_asserts_gateway_read_only": False,
            "requires_human_gateway_configuration_review": True,
            "signed_attestation_required": True,
            "broker_submission_allowed": False,
            "paper_order_submission_allowed": False,
            "live_execution_allowed": False,
            "automatic_promotion_allowed": False,
            "real_money_trading_allowed": False,
        }

    return {
        "engine": ENGINE_VERSION,
        "status": (
            "READY_FOR_INDEPENDENT_REVIEW"
            if ready
            else "BLOCKED"
        ),
        "ready_for_independent_review": ready,
        "attestation_verified": False,
        "gateway_read_only_configuration_independently_attested": False,
        "failure_reasons": failures,
        "handoff_request": handoff_request,
        "broker_submission_allowed": False,
        "paper_order_submission_allowed": False,
        "live_execution_allowed": False,
        "automatic_promotion_allowed": False,
        "real_money_trading_allowed": False,
    }


def build_installed_reviewer_handoff(
    repository_root,
    now=None,
):
    """Build a non-attesting review request from fixed production trust paths."""

    policy_safe, policy_reason = _trusted_root_file(
        DEFAULT_POLICY_PATH,
        max_bytes=8192,
    )
    if not policy_safe:
        return _blocked(
            policy_reason
            or "POLICY_FILE_UNTRUSTED"
        )

    key_safe, key_reason = _trusted_root_file(
        DEFAULT_PUBLIC_KEY_PATH,
        max_bytes=8192,
    )
    if not key_safe:
        return _blocked(
            key_reason
            or "PUBLIC_KEY_FILE_UNTRUSTED"
        )

    try:
        policy = _load_json_bytes(
            DEFAULT_POLICY_PATH.read_bytes()
        )
        public_key_bytes = (
            DEFAULT_PUBLIC_KEY_PATH.read_bytes()
        )
    except (
        OSError,
        UnicodeDecodeError,
        ValueError,
        TypeError,
    ):
        return _blocked(
            "TRUST_ROOT_PARSE_FAILED"
        )

    g0_proof_path = (
        Path(repository_root)
        / DEFAULT_G0_PROOF_RELATIVE_PATH
    )
    try:
        g0_proof = _load_json_bytes(
            g0_proof_path.read_bytes()
        )
    except (
        OSError,
        UnicodeDecodeError,
        ValueError,
        TypeError,
    ):
        return _blocked(
            "G0_RUNTIME_PROOF_UNAVAILABLE"
        )

    runtime_cloud_identity = (
        read_gce_runtime_identity()
    )
    if (
        runtime_cloud_identity.get("status")
        !=
        "VERIFIED"
        or runtime_cloud_identity.get("verified")
        is not True
    ):
        return _blocked(
            "GCE_RUNTIME_IDENTITY_UNVERIFIED"
        )

    current_git_sha = _current_git_sha(
        repository_root
    )
    if current_git_sha is None:
        return _blocked(
            "CURRENT_GIT_SHA_UNAVAILABLE"
        )

    repository_clean = _repository_is_clean(
        repository_root
    )

    openssl_available = (
        OPENSSL_BIN.is_file()
        and os.access(
            OPENSSL_BIN,
            os.X_OK,
        )
    )

    return evaluate_reviewer_handoff_preflight(
        policy=policy,
        public_key_bytes=public_key_bytes,
        current_git_sha=current_git_sha,
        current_instance_name=(
            socket.gethostname().split(".")[0]
        ),
        repository_clean=repository_clean,
        openssl_available=openssl_available,
        g0_proof=g0_proof,
        runtime_cloud_identity=runtime_cloud_identity,
        now=now,
    )
