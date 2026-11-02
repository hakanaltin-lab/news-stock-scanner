#!/usr/bin/env python3
"""Verify the fixed-path independently signed G8.15 adapter source attestation.

This command never signs evidence and has no reviewer private-key path.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from engines.gateway_readonly_attestation_verifier import (
    _artifact_file_safe,
    _current_git_sha,
    _load_json_bytes,
    _repository_is_clean,
    _trusted_root_file,
    _verify_ed25519_signature,
)
from engines.paper_adapter_source_attestation import (
    canonical_signed_payload,
    decode_signature,
    evaluate_source_attestation,
)
from scripts.g6_adapter_source_review import (
    _read_fixed_tracked_source,
)
from scripts.gateway_review_package import (
    read_trusted_runtime_evidence_json,
)
from scripts.ibkr_paper_probe import (
    write_runtime_evidence_atomic,
)


DEFAULT_POLICY_PATH = Path(
    "/etc/aurora/adapter-source-review-policy.json"
)
DEFAULT_PUBLIC_KEY_PATH = Path(
    "/etc/aurora/adapter-source-reviewer-ed25519.pem"
)
DEFAULT_ARTIFACT_PATH = Path(
    "/var/lib/aurora/adapter-source-review-attestation/latest.json"
)
DEFAULT_HANDOFF = (
    "runtime/aurora_g6_source_review_handoff/latest.json"
)
DEFAULT_SOURCE_REVIEW = (
    "runtime/aurora_g6_source_review/latest.json"
)
DEFAULT_OUTPUT = (
    "runtime/aurora_g6_source_attestation/latest.json"
)


def _blocked(reason):
    return {
        "engine": "AURORA G8.15 Adapter Source Attestation CLI",
        "status": "BLOCKED",
        "verified": False,
        "adapter_source_independently_attested": False,
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
        "next_gate": "REPAIR_SIGNED_ADAPTER_SOURCE_ATTESTATION",
    }


def verify_installed_adapter_source_attestation(
    repository_root=REPOSITORY_ROOT,
):
    policy_safe, policy_reason = _trusted_root_file(
        DEFAULT_POLICY_PATH,
        max_bytes=8192,
    )
    if not policy_safe:
        return _blocked(
            policy_reason
            or "SOURCE_REVIEW_POLICY_UNTRUSTED"
        )

    key_safe, key_reason = _trusted_root_file(
        DEFAULT_PUBLIC_KEY_PATH,
        max_bytes=8192,
    )
    if not key_safe:
        return _blocked(
            key_reason
            or "SOURCE_REVIEW_PUBLIC_KEY_UNTRUSTED"
        )

    artifact_safe, artifact_reason = _artifact_file_safe(
        DEFAULT_ARTIFACT_PATH,
        max_bytes=32768,
    )
    if not artifact_safe:
        return _blocked(
            artifact_reason
            or "SOURCE_REVIEW_ATTESTATION_UNTRUSTED"
        )

    try:
        policy_bytes = DEFAULT_POLICY_PATH.read_bytes()
        public_key_bytes = (
            DEFAULT_PUBLIC_KEY_PATH.read_bytes()
        )
        artifact_bytes = DEFAULT_ARTIFACT_PATH.read_bytes()
        policy = _load_json_bytes(
            policy_bytes
        )
        artifact = _load_json_bytes(
            artifact_bytes
        )
    except (
        OSError,
        UnicodeDecodeError,
        ValueError,
        TypeError,
    ):
        return _blocked(
            "SOURCE_REVIEW_TRUST_ROOT_PARSE_FAILED"
        )

    current_git_sha = _current_git_sha(
        repository_root
    )
    clean_before = _repository_is_clean(
        repository_root
    )
    source_text = _read_fixed_tracked_source()
    clean_after = _repository_is_clean(
        repository_root
    )

    if (
        current_git_sha is None
        or clean_before is not True
        or clean_after is not True
        or source_text is None
    ):
        return _blocked(
            "TRACKED_SOURCE_OR_REPOSITORY_STATE_UNTRUSTED"
        )

    payload_bytes = canonical_signed_payload(
        artifact
    )
    signature_bytes = decode_signature(
        artifact.get("signature_b64")
        if isinstance(artifact, dict)
        else None
    )
    signature_valid = (
        payload_bytes is not None
        and signature_bytes is not None
        and _verify_ed25519_signature(
            public_key_bytes,
            payload_bytes,
            signature_bytes,
        )
    )

    return evaluate_source_attestation(
        artifact,
        policy,
        public_key_bytes,
        signature_valid,
        read_trusted_runtime_evidence_json(
            Path(repository_root)
            / DEFAULT_HANDOFF
        ),
        read_trusted_runtime_evidence_json(
            Path(repository_root)
            / DEFAULT_SOURCE_REVIEW
        ),
        source_text,
        current_git_sha,
        True,
    )


def main():
    result = (
        verify_installed_adapter_source_attestation(
            REPOSITORY_ROOT
        )
    )

    try:
        write_runtime_evidence_atomic(
            REPOSITORY_ROOT
            / DEFAULT_OUTPUT,
            result,
        )
    except (
        OSError,
        RuntimeError,
        ValueError,
    ):
        result = _blocked(
            "SOURCE_ATTESTATION_VERIFICATION_WRITE_FAILED"
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
        if result.get("verified") is True
        else 2
    )


if __name__ == "__main__":
    raise SystemExit(main())
