#!/usr/bin/env python3
"""Verify fixed-path independently signed G8.24 offline materializer attestation."""

from __future__ import annotations

import json
from pathlib import Path
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from engines.gateway_readonly_attestation_verifier import (
    _artifact_file_safe,
    _load_json_bytes,
    _repository_is_clean,
    _trusted_root_file,
    _verify_ed25519_signature,
)
from engines.offline_order_request_materializer_attestation import (
    canonical_signed_payload,
    evaluate_materializer_attestation,
)
from engines.paper_adapter_source_attestation import decode_signature
from scripts.gateway_review_package import read_trusted_runtime_evidence_json
from scripts.ibkr_paper_probe import write_runtime_evidence_atomic


DEFAULT_POLICY_PATH = Path(
    "/etc/aurora/offline-materializer-review-policy.json"
)
DEFAULT_PUBLIC_KEY_PATH = Path(
    "/etc/aurora/offline-materializer-reviewer-ed25519.pem"
)
DEFAULT_ARTIFACT_PATH = Path(
    "/var/lib/aurora/offline-materializer-review-attestation/latest.json"
)
DEFAULT_HANDOFF = (
    REPOSITORY_ROOT
    / "runtime/aurora_g6_offline_materializer_handoff/latest.json"
)
DEFAULT_DESIGN = (
    REPOSITORY_ROOT
    / "config/offline_order_request_materializer_design_v1.json"
)
DEFAULT_MATERIALIZER = (
    REPOSITORY_ROOT
    / "engines/offline_order_request_materializer.py"
)
DEFAULT_CLI_SOURCE = (
    REPOSITORY_ROOT
    / "scripts/build_offline_order_request_preview.py"
)
DEFAULT_OUTPUT = (
    REPOSITORY_ROOT
    / "runtime/aurora_g6_offline_materializer_attestation/latest.json"
)


def _blocked(reason):
    return {
        "engine": "AURORA G8.24 Offline Materializer Attestation CLI",
        "status": "BLOCKED",
        "verified": False,
        "offline_materializer_independently_attested": False,
        "reason": reason,
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
        "next_gate": "REPAIR_SIGNED_OFFLINE_MATERIALIZER_ATTESTATION",
    }


def verify_installed_materializer_attestation():
    policy_safe, policy_reason = _trusted_root_file(
        DEFAULT_POLICY_PATH,
        max_bytes=8192,
    )
    if not policy_safe:
        return _blocked(
            policy_reason or "OFFLINE_MATERIALIZER_REVIEW_POLICY_UNTRUSTED"
        )

    key_safe, key_reason = _trusted_root_file(
        DEFAULT_PUBLIC_KEY_PATH,
        max_bytes=8192,
    )
    if not key_safe:
        return _blocked(
            key_reason or "OFFLINE_MATERIALIZER_REVIEW_PUBLIC_KEY_UNTRUSTED"
        )

    artifact_safe, artifact_reason = _artifact_file_safe(
        DEFAULT_ARTIFACT_PATH,
        max_bytes=32768,
    )
    if not artifact_safe:
        return _blocked(
            artifact_reason
            or "OFFLINE_MATERIALIZER_REVIEW_ATTESTATION_UNTRUSTED"
        )

    if _repository_is_clean(REPOSITORY_ROOT) is not True:
        return _blocked("OFFLINE_MATERIALIZER_RUNTIME_EVIDENCE_UNTRUSTED")

    try:
        policy = _load_json_bytes(DEFAULT_POLICY_PATH.read_bytes())
        public_key_bytes = DEFAULT_PUBLIC_KEY_PATH.read_bytes()
        artifact = _load_json_bytes(DEFAULT_ARTIFACT_PATH.read_bytes())
        design = _load_json_bytes(DEFAULT_DESIGN.read_bytes())
        materializer_source = DEFAULT_MATERIALIZER.read_text(encoding="utf-8")
        cli_source = DEFAULT_CLI_SOURCE.read_text(encoding="utf-8")
    except (
        OSError,
        UnicodeDecodeError,
        ValueError,
        TypeError,
    ):
        return _blocked("OFFLINE_MATERIALIZER_REVIEW_TRUST_ROOT_PARSE_FAILED")

    handoff = read_trusted_runtime_evidence_json(DEFAULT_HANDOFF)
    if (
        not handoff
        or _repository_is_clean(REPOSITORY_ROOT) is not True
    ):
        return _blocked("OFFLINE_MATERIALIZER_RUNTIME_EVIDENCE_UNTRUSTED")

    payload = canonical_signed_payload(artifact)
    signature = decode_signature(
        artifact.get("signature_b64")
        if isinstance(artifact, dict)
        else None
    )
    signature_valid = (
        payload is not None
        and signature is not None
        and _verify_ed25519_signature(
            public_key_bytes,
            payload,
            signature,
        )
    )

    return evaluate_materializer_attestation(
        artifact,
        policy,
        public_key_bytes,
        signature_valid,
        handoff,
        design,
        materializer_source,
        cli_source,
        True,
    )


def main():
    result = verify_installed_materializer_attestation()
    try:
        write_runtime_evidence_atomic(DEFAULT_OUTPUT, result)
    except (OSError, RuntimeError, ValueError):
        result = _blocked(
            "OFFLINE_MATERIALIZER_ATTESTATION_VERIFICATION_WRITE_FAILED"
        )

    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("verified") is True else 2


if __name__ == "__main__":
    raise SystemExit(main())
