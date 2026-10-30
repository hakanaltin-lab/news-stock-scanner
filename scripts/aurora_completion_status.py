#!/usr/bin/env python3
"""Fail-closed G0-G4 completion status for the Paper shadow milestone."""

import argparse
from datetime import datetime, timezone
import hashlib
import hmac
import json
import os
from pathlib import Path
import tempfile


DEFAULT_G0_PROOF = "runtime/gcp/latest.json"
DEFAULT_READINESS = "runtime/aurora_readiness/latest.json"
DEFAULT_G4_SHADOW = "runtime/aurora_g4_shadow/latest.json"
DEFAULT_LEDGER_AUDIT = "runtime/aurora_g4_shadow/ledger_audit.json"
DEFAULT_OUTPUT = "runtime/aurora_project_status/latest.json"


def _digest(payload):
    canonical = json.dumps(
        payload or {},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _is_sha256(value):
    text = str(value or "").strip().lower()
    return len(text) == 64 and all(
        character in "0123456789abcdef"
        for character in text
    )


def _utc_datetime(value):
    if isinstance(value, datetime):
        parsed = value
    else:
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


def _age_seconds(value, now):
    parsed = _utc_datetime(value)
    if parsed is None:
        return None
    age = (now - parsed).total_seconds()
    if age < -2:
        return None
    return round(max(age, 0.0), 3)


def _flags_safe(payload, include_automatic=True):
    names = [
        "broker_submission_allowed",
        "paper_order_submission_allowed",
        "live_execution_allowed",
    ]
    if include_automatic:
        names.append("automatic_promotion_allowed")
    return all(payload.get(name) is False for name in names)


def evaluate_completion_status(
    g0_proof,
    readiness,
    g4_shadow,
    ledger_audit,
    now=None,
):
    now = _utc_datetime(now) or datetime.now(timezone.utc)
    g0_proof = g0_proof or {}
    readiness = readiness or {}
    g4_shadow = g4_shadow or {}
    ledger_audit = ledger_audit or {}

    ages = {
        "g0_seconds": _age_seconds(g0_proof.get("generated_at"), now),
        "readiness_seconds": _age_seconds(readiness.get("generated_at"), now),
        "g4_seconds": _age_seconds(g4_shadow.get("generated_at"), now),
        "ledger_audit_seconds": _age_seconds(
            ledger_audit.get("generated_at"), now
        ),
    }
    receipt = g4_shadow.get("ledger_receipt") or {}
    actual_readiness_digest = _digest(readiness)
    recorded_readiness_digest = str(
        g4_shadow.get("readiness_proof_sha256") or ""
    ).strip().lower()
    checks = {
        "g0_g1_verified": (
            g0_proof.get("status") == "G0_G1_VERIFIED"
            and not g0_proof.get("failure_reasons")
            and _flags_safe(g0_proof)
        ),
        "g0_g1_evidence_current": (
            ages["g0_seconds"] is not None
            and ages["g0_seconds"] <= 86400
        ),
        "g2_g3_ready": (
            readiness.get("status") == "READY_FOR_CONTROLLED_DRY_RUN"
            and not readiness.get("failure_reasons")
            and _flags_safe(readiness)
        ),
        "g2_g3_evidence_fresh": (
            ages["readiness_seconds"] is not None
            and ages["readiness_seconds"] <= 120
        ),
        "g4_shadow_accepted": (
            g4_shadow.get("status") == "SHADOW_ACCEPTED"
            and _flags_safe(g4_shadow)
            and receipt.get("recorded") is True
            and receipt.get("duplicate") is False
        ),
        "g4_evidence_fresh": (
            ages["g4_seconds"] is not None
            and ages["g4_seconds"] <= 60
        ),
        "g4_readiness_proof_bound": (
            _is_sha256(recorded_readiness_digest)
            and hmac.compare_digest(
                recorded_readiness_digest,
                actual_readiness_digest,
            )
        ),
        "shadow_ledger_verified": (
            ledger_audit.get("status") == "LEDGER_VERIFIED"
            and not ledger_audit.get("failure_reasons")
            and (ledger_audit.get("record_count") or 0) >= 1
            and _flags_safe(ledger_audit)
        ),
        "ledger_audit_fresh": (
            ages["ledger_audit_seconds"] is not None
            and ages["ledger_audit_seconds"] <= 60
        ),
    }
    failures = [name for name, passed in checks.items() if not passed]
    complete = not failures
    return {
        "engine": "AURORA V8.9.23 G0-G4 Completion Gate",
        "generated_at": now.isoformat(),
        "status": (
            "PAPER_RUNTIME_VALIDATED_SHADOW_ONLY"
            if complete
            else "BLOCKED"
        ),
        "checks": checks,
        "evidence_age": ages,
        "evidence_binding": {
            "readiness_proof_sha256": actual_readiness_digest,
            "g4_recorded_readiness_proof_sha256": (
                recorded_readiness_digest or None
            ),
        },
        "failure_reasons": failures,
        "broker_submission_allowed": False,
        "paper_order_submission_allowed": False,
        "live_execution_allowed": False,
        "automatic_promotion_allowed": False,
        "real_money_trading_allowed": False,
        "next_gate": (
            "MANUAL_PAPER_ORDER_AUTHORIZATION_NOT_GRANTED"
            if complete
            else "REPAIR_G0_G4_EVIDENCE"
        ),
    }


def _read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _write_atomic(path, payload):
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=str(target.parent),
        delete=False,
    ) as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
        temporary = handle.name
    os.replace(temporary, target)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--g0-proof", default=DEFAULT_G0_PROOF)
    parser.add_argument("--readiness", default=DEFAULT_READINESS)
    parser.add_argument("--g4-shadow", default=DEFAULT_G4_SHADOW)
    parser.add_argument("--ledger-audit", default=DEFAULT_LEDGER_AUDIT)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    result = evaluate_completion_status(
        _read_json(args.g0_proof),
        _read_json(args.readiness),
        _read_json(args.g4_shadow),
        _read_json(args.ledger_audit),
    )
    _write_atomic(args.output, result)
    print(json.dumps(result, indent=2, sort_keys=True))
    return (
        0
        if result.get("status") == "PAPER_RUNTIME_VALIDATED_SHADOW_ONLY"
        else 2
    )


if __name__ == "__main__":
    raise SystemExit(main())
