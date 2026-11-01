"""Offline, fail-closed validator for sanitized IBKR Paper probe evidence.

No broker imports, network access, credentials, or order submission.
Read a JSON diagnostic report from stdin or the first CLI file argument.
A parsed report is untrusted input and does NOT prove the source is IBKR.
"""
import json
import sys
from datetime import datetime

REQUIRED_REQUESTS = (
    "managed_accounts", "account_summary", "positions", "open_orders", "executions"
)


def _valid_fingerprint(value):
    return (isinstance(value, str) and value.startswith("IBKR-")
            and len(value) == 15
            and all(c in "0123456789ABCDEF" for c in value[5:]))


def _valid_aware_timestamp(value):
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None


def evaluate_report(report):
    base = {"status": "BLOCKED", "paper_order_submission_allowed": False,
            "live_trading_allowed": False, "evidence_authenticity_verified": False,
            "broker_session_independently_verified": False, "release_approved": False,
            "diagnostic_binding_fields_valid": False}
    if not isinstance(report, dict):
        return {**base, "reason": "INVALID_REPORT"}
    if report.get("status") != "CONNECTED" or report.get("connection_status") != "CONNECTED":
        return {**base, "reason": "BROKER_NOT_CONNECTED"}
    if (report.get("paper_endpoint_safe") is not True
            or report.get("hard_blocked") is not True
            or report.get("live_trading_allowed") is not False
            or report.get("paper_account_verified") is not True):
        return {**base, "reason": "PAPER_GUARD_UNPROVEN"}
    fingerprint = report.get("paper_account_fingerprint")
    if not _valid_fingerprint(fingerprint):
        return {**base, "reason": "INVALID_ACCOUNT_FINGERPRINT"}
    timestamp = report.get("snapshot_generated_at_utc")
    if not _valid_aware_timestamp(timestamp):
        return {**base, "reason": "INVALID_SNAPSHOT_TIMESTAMP"}
    checks = report.get("requests_complete")
    if not isinstance(checks, dict) or any(checks.get(k) is not True for k in REQUIRED_REQUESTS):
        return {**base, "reason": "INCOMPLETE_REQUESTS"}
    return {**base, "status": "READ_ONLY_SNAPSHOT_VALIDATED",
            "reason": "DIAGNOSTIC_ONLY_NO_ORDER_AUTHORIZATION",
            "diagnostic_binding_fields_valid": True,
            "paper_account_fingerprint": fingerprint,
            "snapshot_generated_at_utc": timestamp}


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    try:
        if len(argv) > 1:
            raise ValueError("too many arguments")
        if argv:
            with open(argv[0], "r", encoding="utf-8") as handle:
                report = json.load(handle)
        else:
            report = json.load(sys.stdin)
    except (OSError, ValueError, UnicodeError):
        result = {"status": "BLOCKED", "reason": "INVALID_JSON_EVIDENCE",
                  "paper_order_submission_allowed": False, "live_trading_allowed": False,
                  "evidence_authenticity_verified": False,
                  "broker_session_independently_verified": False,
                  "release_approved": False,
                  "diagnostic_binding_fields_valid": False}
    else:
        result = evaluate_report(report)
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "READ_ONLY_SNAPSHOT_VALIDATED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
