#!/usr/bin/env python3
"""Bind fresh G0-G3 runtime evidence without authorizing any order."""

from datetime import datetime, timezone
import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile


DEFAULT_G0_PROOF = "runtime/gcp/latest.json"
DEFAULT_G2_PROOF = "runtime/ibkr_paper_read_only/latest.json"
DEFAULT_G3_PROOF = "runtime/ibkr_market_data/latest.json"
DEFAULT_OUTPUT = "runtime/aurora_readiness/latest.json"
DEFAULT_MAX_G2_AGE_SECONDS = 300
DEFAULT_MAX_G3_AGE_SECONDS = 60
DEFAULT_MAX_G0_AGE_SECONDS = 86400


def _digest(payload):
    canonical = json.dumps(
        payload or {},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


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
    return round(max(0.0, age), 3)


def evaluate_readiness_bundle(
    g2_proof,
    g3_proof,
    now=None,
    max_g2_age_seconds=DEFAULT_MAX_G2_AGE_SECONDS,
    max_g3_age_seconds=DEFAULT_MAX_G3_AGE_SECONDS,
    g0_proof=None,
    max_g0_age_seconds=DEFAULT_MAX_G0_AGE_SECONDS,
):
    now = _utc_datetime(now) or datetime.now(timezone.utc)
    g2_proof = g2_proof or {}
    g3_proof = g3_proof or {}
    g0_proof = g0_proof or {}

    g2_run_mode = g2_proof.get("run_mode") or {}
    g2_readiness = g2_proof.get("readiness") or {}
    g2_snapshot = g2_proof.get("snapshot") or {}
    g3_snapshot = g3_proof.get("snapshot") or {}
    g3_config = g3_snapshot.get("config") or {}
    g3_account_guard = g3_snapshot.get("paper_account_guard") or {}
    g3_quote = g3_snapshot.get("quote") or {}
    g3_market_gate = g3_proof.get("execution_market_data_gate") or {}

    g0_age = _age_seconds(g0_proof.get("generated_at"), now)
    g2_age = _age_seconds(
        g2_readiness.get("timestamp") or g2_snapshot.get("timestamp"),
        now,
    )
    g3_age = _age_seconds(
        g3_quote.get("market_timestamp") or g3_quote.get("retrieved_at"),
        now,
    )

    checks = {
        "g0_g1_verified": (
            g0_proof.get("status") == "G0_G1_VERIFIED"
            and not g0_proof.get("failure_reasons")
            and all(
                g0_proof.get(name) is False
                for name in (
                    "broker_submission_allowed",
                    "paper_order_submission_allowed",
                    "live_execution_allowed",
                    "automatic_promotion_allowed",
                )
            )
        ),
        "g0_g1_evidence_current": (
            g0_age is not None
            and g0_age <= float(max_g0_age_seconds)
        ),
        "g2_read_only_mode": g2_run_mode.get("mode") == "READ_ONLY",
        "g2_ready": g2_readiness.get("readiness") == "READY_FOR_PAPER_READ_ONLY",
        "g2_no_required_failures": g2_readiness.get("required_failure_count") == 0,
        "g2_order_submission_blocked": (
            g2_readiness.get("paper_order_submission_allowed") is False
            and g2_readiness.get("live_execution_allowed") is False
            and g2_snapshot.get("order_submission_hard_blocked") is True
        ),
        "g2_evidence_fresh": (
            g2_age is not None
            and g2_age <= float(max_g2_age_seconds)
        ),
        "g3_realtime_ready": g3_snapshot.get("status") == "REALTIME_READY",
        "g3_paper_loopback_endpoint": (
            g3_config.get("mode") == "PAPER"
            and g3_config.get("endpoint_safe") is True
            and g3_config.get("host") == "127.0.0.1"
            and g3_config.get("port") == 4002
        ),
        "g3_paper_account_verified": (
            g3_account_guard.get("paper_account_verified") is True
        ),
        "g3_realtime_quote": (
            g3_quote.get("source") == "IBKR_REALTIME"
            and g3_quote.get("market_data_type_name") == "REALTIME"
            and g3_quote.get("execution_eligible") is True
        ),
        "g3_execution_data_gate_passed": (
            g3_market_gate.get("decision") == "PASS"
            and g3_market_gate.get("execution_eligible") is True
        ),
        "g3_order_submission_blocked": (
            g3_proof.get("broker_submission_allowed") is False
            and g3_proof.get("paper_order_submission_allowed") is False
            and g3_proof.get("live_execution_allowed") is False
        ),
        "g3_evidence_fresh": (
            g3_age is not None
            and g3_age <= float(max_g3_age_seconds)
        ),
    }
    failures = [name for name, passed in checks.items() if not passed]
    ready = not failures

    return {
        "engine": "AURORA V8.9.25 G0-G3 Runtime Readiness Bundle",
        "generated_at": now.isoformat(),
        "status": "READY_FOR_CONTROLLED_DRY_RUN" if ready else "NOT_READY",
        "checks": checks,
        "failure_reasons": failures,
        "g0_g1_evidence_age_seconds": g0_age,
        "g2_evidence_age_seconds": g2_age,
        "g3_evidence_age_seconds": g3_age,
        "symbol": g3_proof.get("symbol"),
        "g0_g1_proof_sha256": _digest(g0_proof),
        "g2_paper_read_only_proof_sha256": _digest(g2_proof),
        "g3_market_data_proof_sha256": _digest(g3_proof),
        "broker_submission_allowed": False,
        "paper_order_submission_allowed": False,
        "live_execution_allowed": False,
        "automatic_promotion_allowed": False,
        "next_milestone": (
            "G4_CONTROLLED_DRY_RUN"
            if ready
            else "REPAIR_G0_G3_RUNTIME_EVIDENCE"
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
    parser.add_argument("--g2-proof", default=DEFAULT_G2_PROOF)
    parser.add_argument("--g3-proof", default=DEFAULT_G3_PROOF)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)

    result = evaluate_readiness_bundle(
        _read_json(args.g2_proof),
        _read_json(args.g3_proof),
        g0_proof=_read_json(args.g0_proof),
    )
    _write_atomic(args.output, result)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "READY_FOR_CONTROLLED_DRY_RUN" else 2


if __name__ == "__main__":
    raise SystemExit(main())
