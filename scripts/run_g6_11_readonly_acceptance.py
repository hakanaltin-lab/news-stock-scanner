#!/usr/bin/env python3
"""One-command G6.11 IBKR Paper read-only acceptance evidence runner.

This runner:
- performs local security checks;
- creates/loads a protected local HMAC evidence key;
- loads the raw Paper account allowlist only from protected local state/env;
- invokes the existing read-only probe;
- validates the sanitized report offline;
- writes only sanitized evidence artifacts.

It never submits orders, changes firewall rules, or enables LIVE trading.
"""

import argparse
import contextlib
from datetime import datetime, timezone
import io
import json
import os
from pathlib import Path
import re
import secrets
import stat
import subprocess
import sys
import tempfile

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from scripts import ibkr_paper_readonly_probe as probe
from scripts.paper_readonly_acceptance_validator import evaluate_report
from scripts.vps_local_security_preflight import evaluate as security_evaluate


DEFAULT_CONFIG_DIR = Path.home() / ".config" / "aurora"
DEFAULT_KEY_FILE = DEFAULT_CONFIG_DIR / "ibkr_evidence_hmac.key"
DEFAULT_ALLOWLIST_FILE = DEFAULT_CONFIG_DIR / "ibkr_paper_account_allowlist"
DEFAULT_EVIDENCE_DIR = REPOSITORY_ROOT / "runtime" / "g6_11_readonly_evidence"


def _safe_result(status, reason, **extra):
    return {
        "status": status,
        "reason": reason,
        "paper_order_submission_allowed": False,
        "live_trading_allowed": False,
        "release_approved": False,
        **extra,
    }


def _git_sha(repo):
    try:
        result = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    value = result.stdout.strip() if result.returncode == 0 else ""
    return value if re.fullmatch(r"[0-9a-f]{40}", value) else None


def _mode(path):
    try:
        return stat.S_IMODE(path.stat().st_mode)
    except OSError:
        return None


def _write_private(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(path.parent, 0o700)
    fd, temporary = tempfile.mkstemp(
        prefix=f".{path.name}.",
        dir=str(path.parent),
        text=True,
    )
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            if not text.endswith("\n"):
                handle.write("\n")
        os.replace(temporary, path)
        os.chmod(path, 0o600)
    except Exception:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def _load_or_create_hmac_key(path):
    path = Path(path)
    if path.exists():
        if _mode(path) != 0o600:
            return None, "EVIDENCE_HMAC_KEY_PERMISSIONS_MUST_BE_0600"
        try:
            value = path.read_text(encoding="utf-8").strip()
        except OSError:
            return None, "EVIDENCE_HMAC_KEY_UNREADABLE"
    else:
        try:
            value = secrets.token_hex(32)
            _write_private(path, value)
        except OSError:
            return None, "EVIDENCE_HMAC_KEY_CREATE_FAILED"

    if not re.fullmatch(r"[0-9a-fA-F]{64}", value):
        return None, "EVIDENCE_HMAC_KEY_INVALID"
    return value, None


def _load_allowlist(path):
    env_value = os.environ.get("AURORA_IBKR_PAPER_ACCOUNT_ALLOWLIST", "").strip()
    if env_value:
        return env_value, None

    path = Path(path)
    if not path.exists():
        return None, "PAPER_ACCOUNT_ALLOWLIST_FILE_REQUIRED"
    if _mode(path) != 0o600:
        return None, "PAPER_ACCOUNT_ALLOWLIST_PERMISSIONS_MUST_BE_0600"
    try:
        value = path.read_text(encoding="utf-8").strip()
    except OSError:
        return None, "PAPER_ACCOUNT_ALLOWLIST_UNREADABLE"
    items = [item.strip() for item in value.split(",") if item.strip()]
    if not items or any(
        not item.isascii()
        or len(item) > 32
        or not all(character.isalnum() or character in "-_" for character in item)
        for item in items
    ):
        return None, "PAPER_ACCOUNT_ALLOWLIST_INVALID"
    return ",".join(items), None


def _parse_probe_output(text):
    try:
        payload = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return None
    return payload if isinstance(payload, dict) else None


def _artifact_name(prefix, captured_at):
    stamp = captured_at.strftime("%Y%m%dT%H%M%SZ")
    return f"{stamp}_{prefix}.json"


def run(
    repo_path=REPOSITORY_ROOT,
    evidence_dir=DEFAULT_EVIDENCE_DIR,
    key_file=DEFAULT_KEY_FILE,
    allowlist_file=DEFAULT_ALLOWLIST_FILE,
):
    repo_path = Path(repo_path).resolve()
    evidence_dir = Path(evidence_dir).resolve()
    captured_at = datetime.now(timezone.utc)
    git_sha = _git_sha(repo_path)
    if git_sha is None:
        return _safe_result("BLOCKED", "REPOSITORY_GIT_SHA_UNAVAILABLE")

    security = security_evaluate(
        repo_path=repo_path,
        expected_sha=git_sha,
    )
    try:
        evidence_dir.mkdir(parents=True, exist_ok=True)
        os.chmod(evidence_dir, 0o700)
        _write_private(
            evidence_dir / _artifact_name("local_security", captured_at),
            json.dumps(security, sort_keys=True),
        )
    except OSError:
        return _safe_result("BLOCKED", "EVIDENCE_DIRECTORY_UNAVAILABLE")

    if security.get("status") != "LOCAL_SECURITY_READY":
        return _safe_result(
            "BLOCKED",
            "LOCAL_SECURITY_PREFLIGHT_FAILED",
            git_sha=git_sha,
        )

    hmac_key, key_error = _load_or_create_hmac_key(key_file)
    if key_error:
        return _safe_result("BLOCKED", key_error, git_sha=git_sha)

    allowlist, allowlist_error = _load_allowlist(allowlist_file)
    if allowlist_error:
        return _safe_result("BLOCKED", allowlist_error, git_sha=git_sha)

    environment = {
        "AURORA_IBKR_ENABLED": "true",
        "AURORA_IBKR_MODE": "PAPER",
        "AURORA_IBKR_HOST": "127.0.0.1",
        "AURORA_IBKR_PORT": "4002",
        "AURORA_IBKR_EVIDENCE_HMAC_KEY": hmac_key,
        "AURORA_IBKR_PAPER_ACCOUNT_ALLOWLIST": allowlist,
    }

    previous = {key: os.environ.get(key) for key in environment}
    os.environ.update(environment)
    output = io.StringIO()
    try:
        with contextlib.redirect_stdout(output):
            probe_exit = probe.main()
    except Exception:
        probe_exit = 1
        output = io.StringIO(
            json.dumps(_safe_result("ERROR", "READ_ONLY_PROBE_RUNNER_EXCEPTION"))
        )
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    probe_payload = _parse_probe_output(output.getvalue())
    if probe_payload is None:
        probe_payload = _safe_result("ERROR", "INVALID_SANITIZED_PROBE_OUTPUT")
        probe_exit = 1

    probe_path = evidence_dir / _artifact_name("sanitized_probe", captured_at)
    try:
        _write_private(probe_path, json.dumps(probe_payload, sort_keys=True))
    except OSError:
        return _safe_result("BLOCKED", "PROBE_EVIDENCE_WRITE_FAILED", git_sha=git_sha)

    validation = evaluate_report(probe_payload)
    validation_path = evidence_dir / _artifact_name("offline_validation", captured_at)
    try:
        _write_private(
            validation_path,
            json.dumps(validation, sort_keys=True),
        )
    except OSError:
        return _safe_result("BLOCKED", "VALIDATION_EVIDENCE_WRITE_FAILED", git_sha=git_sha)

    bundle = {
        "status": (
            "G6_11_READ_ONLY_EVIDENCE_CAPTURED"
            if probe_exit == 0
            and validation.get("status") == "READ_ONLY_SNAPSHOT_VALIDATED"
            else "BLOCKED"
        ),
        "captured_at_utc": captured_at.isoformat(),
        "git_sha": git_sha,
        "local_security": security,
        "sanitized_probe": probe_payload,
        "offline_validation": validation,
        "paper_order_submission_allowed": False,
        "live_trading_allowed": False,
        "release_approved": False,
        "evidence_authenticity_verified": False,
        "broker_session_independently_verified": False,
    }
    bundle_path = evidence_dir / _artifact_name("acceptance_bundle", captured_at)
    try:
        _write_private(bundle_path, json.dumps(bundle, sort_keys=True))
    except OSError:
        return _safe_result("BLOCKED", "BUNDLE_EVIDENCE_WRITE_FAILED", git_sha=git_sha)

    if bundle["status"] != "G6_11_READ_ONLY_EVIDENCE_CAPTURED":
        return _safe_result(
            "BLOCKED",
            "READ_ONLY_ACCEPTANCE_NOT_PASSED",
            git_sha=git_sha,
            bundle_path=str(bundle_path),
        )

    return _safe_result(
        "G6_11_READ_ONLY_EVIDENCE_CAPTURED",
        "SANITIZED_READ_ONLY_EVIDENCE_READY_FOR_INDEPENDENT_REVIEW",
        git_sha=git_sha,
        bundle_path=str(bundle_path),
    )


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=str(REPOSITORY_ROOT))
    parser.add_argument("--evidence-dir", default=str(DEFAULT_EVIDENCE_DIR))
    parser.add_argument("--key-file", default=str(DEFAULT_KEY_FILE))
    parser.add_argument("--allowlist-file", default=str(DEFAULT_ALLOWLIST_FILE))
    args = parser.parse_args(argv)

    result = run(
        repo_path=args.repo,
        evidence_dir=args.evidence_dir,
        key_file=args.key_file,
        allowlist_file=args.allowlist_file,
    )
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "G6_11_READ_ONLY_EVIDENCE_CAPTURED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
