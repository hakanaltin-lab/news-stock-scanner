"""Verify independently signed IB Gateway/TWS Read-Only attestations.

Security boundary:
- AURORA never creates or self-asserts a positive attestation.
- Production paths are fixed and cannot be overridden by environment variables.
- Reviewer trust is rooted in root-owned policy/public-key files.
- Only detached Ed25519 signatures verified by /usr/bin/openssl are accepted.
- Any parsing, binding, freshness, filesystem, or signature failure is fail-closed.
"""

from __future__ import annotations

import base64
import binascii
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import stat
import subprocess
import tempfile
from uuid import UUID


ENGINE_VERSION = "AURORA G7.5 Gateway Read-Only Attestation Verifier"

DEFAULT_POLICY_PATH = Path(
    "/etc/aurora/gateway-readonly-attestation-policy.json"
)
DEFAULT_PUBLIC_KEY_PATH = Path(
    "/etc/aurora/gateway-readonly-reviewer-ed25519.pem"
)
DEFAULT_ARTIFACT_PATH = Path(
    "/var/lib/aurora/gateway-readonly-attestation/latest.json"
)
OPENSSL_BIN = Path("/usr/bin/openssl")

ATTESTATION_TYPE = "IBKR_GATEWAY_API_READ_ONLY_V1"
SIGNATURE_ALGORITHM = "ED25519"

_ARTIFACT_FIELDS = {
    "schema_version",
    "attestation_id",
    "attestation_type",
    "decision",
    "reviewer_id",
    "captured_at_utc",
    "expires_at_utc",
    "git_sha",
    "instance_name",
    "zone",
    "broker_mode",
    "gateway_port",
    "read_only_api_enabled",
    "evidence_sha256",
    "signature_algorithm",
    "signature_b64",
}

_POLICY_FIELDS = {
    "policy_version",
    "reviewer_id",
    "public_key_sha256",
    "expected_instance_name",
    "expected_zone",
    "max_attestation_age_seconds",
    "allowed_clock_skew_seconds",
}

_HEX_40 = re.compile(r"^[0-9a-f]{40}$")
_HEX_64 = re.compile(r"^[0-9a-f]{64}$")
_REVIEWER_ID = re.compile(r"^[A-Za-z0-9._@+-]{3,128}$")
_INSTANCE_NAME = re.compile(r"^[a-z][a-z0-9-]{0,62}$")
_ZONE = re.compile(r"^[a-z0-9-]{3,64}$")


class DuplicateJsonKeyError(ValueError):
    """Raised when signed JSON contains ambiguous duplicate keys."""


def _reject_duplicate_object_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateJsonKeyError(
                f"duplicate JSON key: {key}"
            )
        result[key] = value
    return result


def _load_json_bytes(raw):
    if not isinstance(raw, (bytes, bytearray)):
        raise TypeError("JSON input must be bytes")
    return json.loads(
        bytes(raw).decode("utf-8"),
        object_pairs_hook=_reject_duplicate_object_pairs,
    )


def _utc_datetime(value):
    text = str(value or "").strip()
    if not text:
        return None
    if not (
        text.endswith("Z")
        or text.endswith("+00:00")
    ):
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


def _is_uuid4(value):
    text = str(value or "").strip()
    try:
        parsed = UUID(text)
    except (ValueError, AttributeError):
        return False
    return (
        parsed.version == 4
        and text == str(parsed)
    )


def _canonical_signed_payload(artifact):
    if not isinstance(artifact, dict):
        raise TypeError("artifact must be a dictionary")
    payload = {
        key: value
        for key, value in artifact.items()
        if key != "signature_b64"
    }
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")


def _decode_signature(value):
    text = str(value or "").strip()
    try:
        decoded = base64.b64decode(
            text,
            validate=True,
        )
    except (binascii.Error, ValueError):
        return None
    if len(decoded) != 64:
        return None
    return decoded


def _sha256_bytes(raw):
    return hashlib.sha256(raw).hexdigest()


def _trusted_root_file(path, max_bytes):
    path = Path(path)
    try:
        link_info = path.lstat()
        parent_info = path.parent.stat()
        info = path.stat()
    except OSError:
        return False, "MISSING_TRUSTED_FILE"

    if stat.S_ISLNK(link_info.st_mode):
        return False, "TRUSTED_PATH_SYMLINK_FORBIDDEN"
    if not stat.S_ISDIR(parent_info.st_mode):
        return False, "TRUSTED_PARENT_NOT_DIRECTORY"
    if parent_info.st_uid != 0:
        return False, "TRUSTED_PARENT_NOT_ROOT_OWNED"
    if parent_info.st_mode & 0o022:
        return False, "TRUSTED_PARENT_GROUP_OR_WORLD_WRITABLE"
    if not stat.S_ISREG(info.st_mode):
        return False, "TRUSTED_PATH_NOT_REGULAR_FILE"
    if info.st_uid != 0:
        return False, "TRUSTED_FILE_NOT_ROOT_OWNED"
    if info.st_mode & 0o022:
        return False, "TRUSTED_FILE_GROUP_OR_WORLD_WRITABLE"
    if info.st_size <= 0 or info.st_size > max_bytes:
        return False, "TRUSTED_FILE_SIZE_INVALID"
    return True, None


def _artifact_file_safe(path, max_bytes=32768):
    path = Path(path)
    try:
        link_info = path.lstat()
        parent_info = path.parent.stat()
        info = path.stat()
    except OSError:
        return False, "ATTESTATION_ARTIFACT_MISSING"

    if stat.S_ISLNK(link_info.st_mode):
        return False, "ATTESTATION_ARTIFACT_SYMLINK_FORBIDDEN"
    if not stat.S_ISDIR(parent_info.st_mode):
        return False, "ATTESTATION_PARENT_NOT_DIRECTORY"
    if parent_info.st_mode & 0o002:
        return False, "ATTESTATION_PARENT_WORLD_WRITABLE"
    if not stat.S_ISREG(info.st_mode):
        return False, "ATTESTATION_PATH_NOT_REGULAR_FILE"
    if info.st_mode & 0o002:
        return False, "ATTESTATION_ARTIFACT_WORLD_WRITABLE"
    if info.st_size <= 0 or info.st_size > max_bytes:
        return False, "ATTESTATION_ARTIFACT_SIZE_INVALID"
    return True, None


def _verify_ed25519_signature(
    public_key_bytes,
    payload_bytes,
    signature_bytes,
):
    if not OPENSSL_BIN.is_file():
        return False

    if (
        not isinstance(public_key_bytes, bytes)
        or not isinstance(payload_bytes, bytes)
        or not isinstance(signature_bytes, bytes)
    ):
        return False

    try:
        with tempfile.TemporaryDirectory(
            prefix="aurora-attestation-"
        ) as directory:
            directory = Path(directory)
            public_key_file = directory / "reviewer-public.pem"
            payload_file = directory / "payload.json"
            signature_file = directory / "signature.bin"

            public_key_file.write_bytes(public_key_bytes)
            payload_file.write_bytes(payload_bytes)
            signature_file.write_bytes(signature_bytes)

            os.chmod(public_key_file, 0o600)
            os.chmod(payload_file, 0o600)
            os.chmod(signature_file, 0o600)

            completed = subprocess.run(
                [
                    str(OPENSSL_BIN),
                    "pkeyutl",
                    "-verify",
                    "-pubin",
                    "-inkey",
                    str(public_key_file),
                    "-rawin",
                    "-in",
                    str(payload_file),
                    "-sigfile",
                    str(signature_file),
                ],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
                timeout=5,
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
        return False

    return completed.returncode == 0


def evaluate_gateway_readonly_attestation(
    artifact,
    policy,
    current_git_sha,
    current_instance_name,
    public_key_bytes,
    signature_valid,
    repository_clean=True,
    now=None,
):
    """Evaluate parsed, already-loaded evidence without trusting caller claims."""

    now = (
        now.astimezone(timezone.utc)
        if isinstance(now, datetime) and now.tzinfo is not None
        else datetime.now(timezone.utc)
    )

    failures = []

    def require(name, condition):
        if not condition:
            failures.append(name)

    artifact_is_dict = isinstance(artifact, dict)
    policy_is_dict = isinstance(policy, dict)

    require("artifact_is_object", artifact_is_dict)
    require("policy_is_object", policy_is_dict)

    if not artifact_is_dict:
        artifact = {}
    if not policy_is_dict:
        policy = {}

    require(
        "artifact_field_set_exact",
        set(artifact) == _ARTIFACT_FIELDS,
    )
    require(
        "policy_field_set_exact",
        set(policy) == _POLICY_FIELDS,
    )

    require(
        "artifact_schema_version",
        type(artifact.get("schema_version")) is int
        and artifact.get("schema_version") == 1,
    )
    require(
        "policy_version",
        type(policy.get("policy_version")) is int
        and policy.get("policy_version") == 1,
    )
    require(
        "attestation_id_uuid4",
        _is_uuid4(artifact.get("attestation_id")),
    )
    require(
        "attestation_type",
        artifact.get("attestation_type") == ATTESTATION_TYPE,
    )
    require(
        "decision_attested",
        artifact.get("decision") == "ATTESTED",
    )
    require(
        "signature_algorithm",
        artifact.get("signature_algorithm") == SIGNATURE_ALGORITHM,
    )

    reviewer_id = artifact.get("reviewer_id")
    policy_reviewer_id = policy.get("reviewer_id")
    require(
        "reviewer_id_format",
        isinstance(reviewer_id, str)
        and bool(_REVIEWER_ID.fullmatch(reviewer_id)),
    )
    require(
        "reviewer_matches_policy",
        reviewer_id == policy_reviewer_id,
    )

    git_sha = str(artifact.get("git_sha") or "").strip().lower()
    current_git_sha = str(current_git_sha or "").strip().lower()
    require(
        "artifact_git_sha_format",
        bool(_HEX_40.fullmatch(git_sha)),
    )
    require(
        "current_git_sha_format",
        bool(_HEX_40.fullmatch(current_git_sha)),
    )
    require(
        "git_sha_bound",
        bool(git_sha)
        and git_sha == current_git_sha,
    )
    require(
        "repository_clean",
        repository_clean is True,
    )

    instance_name = artifact.get("instance_name")
    policy_instance = policy.get("expected_instance_name")
    require(
        "instance_name_format",
        isinstance(instance_name, str)
        and bool(_INSTANCE_NAME.fullmatch(instance_name)),
    )
    require(
        "instance_matches_policy",
        instance_name == policy_instance,
    )
    require(
        "runtime_instance_bound",
        instance_name == str(current_instance_name or "").strip(),
    )

    zone = artifact.get("zone")
    require(
        "zone_format",
        isinstance(zone, str)
        and bool(_ZONE.fullmatch(zone)),
    )
    require(
        "zone_matches_policy",
        zone == policy.get("expected_zone"),
    )

    require(
        "paper_mode_only",
        artifact.get("broker_mode") == "PAPER",
    )
    require(
        "paper_gateway_port",
        type(artifact.get("gateway_port")) is int
        and artifact.get("gateway_port") == 4002,
    )
    require(
        "read_only_enabled",
        artifact.get("read_only_api_enabled") is True,
    )

    evidence_sha256 = str(
        artifact.get("evidence_sha256") or ""
    ).strip().lower()
    require(
        "evidence_sha256_valid",
        bool(_HEX_64.fullmatch(evidence_sha256))
        and evidence_sha256 != ("0" * 64),
    )

    public_key_sha256 = (
        _sha256_bytes(public_key_bytes)
        if isinstance(public_key_bytes, bytes)
        else ""
    )
    policy_key_sha256 = str(
        policy.get("public_key_sha256") or ""
    ).strip().lower()
    require(
        "policy_public_key_sha256_valid",
        bool(_HEX_64.fullmatch(policy_key_sha256))
        and policy_key_sha256 != ("0" * 64),
    )
    require(
        "public_key_matches_policy",
        bool(public_key_sha256)
        and public_key_sha256 == policy_key_sha256,
    )

    captured = _utc_datetime(
        artifact.get("captured_at_utc")
    )
    expires = _utc_datetime(
        artifact.get("expires_at_utc")
    )

    max_age = policy.get(
        "max_attestation_age_seconds"
    )
    clock_skew = policy.get(
        "allowed_clock_skew_seconds"
    )
    max_age_valid = (
        type(max_age) is int
        and 60 <= max_age <= 86400
    )
    clock_skew_valid = (
        type(clock_skew) is int
        and 0 <= clock_skew <= 300
    )
    require(
        "policy_max_age_valid",
        max_age_valid,
    )
    require(
        "policy_clock_skew_valid",
        clock_skew_valid,
    )
    require(
        "captured_at_valid",
        captured is not None,
    )
    require(
        "expires_at_valid",
        expires is not None,
    )

    if (
        captured is not None
        and expires is not None
        and max_age_valid
        and clock_skew_valid
    ):
        age_seconds = (
            now - captured
        ).total_seconds()
        validity_seconds = (
            expires - captured
        ).total_seconds()

        require(
            "capture_not_in_future",
            age_seconds >= -clock_skew,
        )
        require(
            "attestation_not_expired",
            now <= expires,
        )
        require(
            "attestation_age_within_policy",
            age_seconds <= max_age,
        )
        require(
            "attestation_validity_window_positive",
            validity_seconds > 0,
        )
        require(
            "attestation_validity_window_within_policy",
            validity_seconds <= max_age,
        )

    require(
        "signature_encoding_valid",
        _decode_signature(
            artifact.get("signature_b64")
        )
        is not None,
    )
    require(
        "ed25519_signature_valid",
        signature_valid is True,
    )

    verified = not failures

    return {
        "engine": ENGINE_VERSION,
        "verified": verified,
        "status": (
            "VERIFIED"
            if verified
            else "BLOCKED"
        ),
        "gateway_read_only_configuration_independently_attested": (
            verified
        ),
        "failure_reasons": failures,
        "attestation_id": (
            artifact.get("attestation_id")
            if verified
            else None
        ),
        "reviewer_id": (
            reviewer_id
            if verified
            else None
        ),
        "captured_at_utc": (
            artifact.get("captured_at_utc")
            if verified
            else None
        ),
        "expires_at_utc": (
            artifact.get("expires_at_utc")
            if verified
            else None
        ),
        "git_sha": (
            git_sha
            if verified
            else None
        ),
        "evidence_sha256": (
            evidence_sha256
            if verified
            else None
        ),
    }


def _blocked(reason):
    return {
        "engine": ENGINE_VERSION,
        "verified": False,
        "status": "BLOCKED",
        "gateway_read_only_configuration_independently_attested": False,
        "failure_reasons": [reason],
        "attestation_id": None,
        "reviewer_id": None,
        "captured_at_utc": None,
        "expires_at_utc": None,
        "git_sha": None,
        "evidence_sha256": None,
    }


def _current_git_sha(repository_root):
    try:
        completed = subprocess.run(
            [
                "/usr/bin/git",
                "-C",
                str(Path(repository_root)),
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
    if completed.returncode != 0:
        return None
    if not _HEX_40.fullmatch(value):
        return None
    return value


def _repository_is_clean(repository_root):
    try:
        completed = subprocess.run(
            [
                "/usr/bin/git",
                "-C",
                str(Path(repository_root)),
                "status",
                "--porcelain",
                "--untracked-files=no",
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
        return False

    return (
        completed.returncode == 0
        and completed.stdout.strip() == ""
    )


def verify_installed_gateway_readonly_attestation(
    repository_root,
    now=None,
):
    """Verify the fixed-path production attestation. No path/env overrides."""

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

    artifact_safe, artifact_reason = _artifact_file_safe(
        DEFAULT_ARTIFACT_PATH,
    )
    if not artifact_safe:
        return _blocked(
            artifact_reason
            or "ATTESTATION_ARTIFACT_UNTRUSTED"
        )

    try:
        policy_bytes = DEFAULT_POLICY_PATH.read_bytes()
        public_key_bytes = DEFAULT_PUBLIC_KEY_PATH.read_bytes()
        artifact_bytes = DEFAULT_ARTIFACT_PATH.read_bytes()

        policy = _load_json_bytes(policy_bytes)
        artifact = _load_json_bytes(artifact_bytes)
    except (
        OSError,
        UnicodeDecodeError,
        json.JSONDecodeError,
        DuplicateJsonKeyError,
        TypeError,
    ):
        return _blocked(
            "ATTESTATION_INPUT_PARSE_FAILED"
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
    if not repository_clean:
        return _blocked(
            "REPOSITORY_NOT_CLEAN"
        )

    signature = _decode_signature(
        artifact.get("signature_b64")
        if isinstance(artifact, dict)
        else None
    )
    if signature is None:
        signature_valid = False
    else:
        try:
            payload = _canonical_signed_payload(
                artifact
            )
        except (TypeError, ValueError):
            payload = b""

        signature_valid = (
            bool(payload)
            and _verify_ed25519_signature(
                public_key_bytes,
                payload,
                signature,
            )
        )

    return evaluate_gateway_readonly_attestation(
        artifact=artifact,
        policy=policy,
        current_git_sha=current_git_sha,
        current_instance_name=socket.gethostname().split(".")[0],
        public_key_bytes=public_key_bytes,
        signature_valid=signature_valid,
        repository_clean=repository_clean,
        now=now,
    )
