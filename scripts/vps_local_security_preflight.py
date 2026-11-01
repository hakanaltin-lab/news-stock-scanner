"""Offline/local VPS security preflight for AURORA Paper readiness.

This tool performs local process/filesystem/socket inspection only.
It does not import broker APIs, open network connections, authenticate to IBKR,
change firewall rules, or submit orders.
"""
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

DEFAULT_REPO = Path("/opt/aurora/news-stock-scanner")
DEFAULT_IB_GATEWAY = Path.home() / "Jts" / "ibgateway" / "1050"

def _run(args):
    try:
        return subprocess.run(args, capture_output=True, text=True, timeout=10, check=False)
    except (OSError, subprocess.SubprocessError):
        return None

def _git_sha(repo_path):
    if not repo_path.is_dir() or shutil.which("git") is None:
        return None
    result = _run(["git", "-C", str(repo_path), "rev-parse", "HEAD"])
    if result is None or result.returncode != 0:
        return None
    sha = result.stdout.strip()
    return sha if re.fullmatch(r"[0-9a-f]{40}", sha) else None

def _listeners():
    if shutil.which("ss") is None:
        return []
    result = _run(["ss", "-ltnp"])
    if result is None or result.returncode != 0:
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]

def _port_bindings(lines, port):
    suffix = f":{port}"
    bindings = []
    for line in lines:
        parts = line.split()
        if len(parts) < 4:
            continue
        local = parts[3]
        if local.endswith(suffix):
            bindings.append(local)
    return bindings

def _local_only(bindings):
    if not bindings:
        return False
    allowed_prefixes = ("127.0.0.1:", "[::1]:", "::1:")
    return all(binding.startswith(allowed_prefixes) for binding in bindings)

def _gateway_installed(root):
    if not root.exists():
        return False
    candidates = ("ibgateway", "ibgateway.vmoptions", "jars")
    return any((root / name).exists() for name in candidates)

def _gateway_running():
    result = _run(["ps", "-eo", "args="])
    if result is None or result.returncode != 0:
        return False
    lowered = result.stdout.lower()
    return "ibgateway" in lowered or "ib gateway" in lowered

def evaluate(repo_path=DEFAULT_REPO, gateway_root=DEFAULT_IB_GATEWAY, expected_sha=None, listener_lines=None):
    repo_path = Path(repo_path)
    gateway_root = Path(gateway_root)
    listeners = _listeners() if listener_lines is None else list(listener_lines)
    sha = _git_sha(repo_path)
    vnc = _port_bindings(listeners, 5902)
    novnc = _port_bindings(listeners, 6080)
    api = _port_bindings(listeners, 4002)
    report = {
        "status": "BLOCKED",
        "repo_present": repo_path.is_dir(),
        "repo_sha": sha,
        "repo_sha_matches_expected": bool(expected_sha and sha == expected_sha),
        "vnc_5902_bindings": vnc,
        "vnc_5902_local_only": _local_only(vnc),
        "novnc_6080_bindings": novnc,
        "novnc_6080_local_only": _local_only(novnc),
        "ib_gateway_installed": _gateway_installed(gateway_root),
        "ib_gateway_running": _gateway_running(),
        "paper_api_4002_bindings": api,
        "paper_api_4002_local_only": _local_only(api) if api else False,
        "paper_order_submission_allowed": False,
        "live_trading_allowed": False,
        "broker_auth_verified": False,
        "release_approved": False,
    }
    security_ready = (
        report["repo_present"]
        and report["vnc_5902_local_only"]
        and report["novnc_6080_local_only"]
        and report["ib_gateway_installed"]
    )
    if expected_sha:
        security_ready = security_ready and report["repo_sha_matches_expected"]
    if security_ready:
        report["status"] = "LOCAL_SECURITY_READY"
        report["reason"] = "BROKER_LOGIN_AND_READ_ONLY_API_ACCEPTANCE_STILL_REQUIRED"
    else:
        report["reason"] = "LOCAL_SECURITY_PREREQUISITES_INCOMPLETE"
    return report

def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    expected_sha = os.environ.get("AURORA_EXPECTED_SHA")
    if len(argv) > 1:
        print(json.dumps({
            "status": "BLOCKED",
            "reason": "USAGE",
            "paper_order_submission_allowed": False,
            "live_trading_allowed": False,
            "release_approved": False,
        }, sort_keys=True))
        return 2
    repo_path = Path(argv[0]) if argv else DEFAULT_REPO
    report = evaluate(repo_path=repo_path, expected_sha=expected_sha)
    print(json.dumps(report, sort_keys=True))
    return 0 if report["status"] == "LOCAL_SECURITY_READY" else 1

if __name__ == "__main__":
    raise SystemExit(main())
