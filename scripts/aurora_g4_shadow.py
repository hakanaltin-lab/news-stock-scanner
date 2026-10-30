#!/usr/bin/env python3
"""Create one audited G4 shadow order from fresh G2/G3 evidence.

This module has no broker submission path. It consumes an explicit operator
intent and the latest fail-closed readiness artifacts, then delegates only to
the broker-independent dry-run engine.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from engines.dry_run_execution_engine import DryRunExecutionEngine
from engines.shadow_audit_ledger import ShadowAuditLedger


DEFAULT_READINESS_PROOF = "runtime/aurora_readiness/latest.json"
DEFAULT_MARKET_DATA_PROOF = "runtime/ibkr_market_data/latest.json"
DEFAULT_OUTPUT = "runtime/aurora_g4_shadow/latest.json"
DEFAULT_LEDGER = "runtime/aurora_g4_shadow/shadow_audit.sqlite3"
DEFAULT_MAX_READINESS_AGE_SECONDS = 30


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


def _digest(payload):
    canonical = json.dumps(
        payload or {},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _block(reason, **extra):
    return {
        "engine": "AURORA V8.9.17 G4 Runtime Shadow Gate",
        "status": "BLOCKED",
        "reason": reason,
        "broker_submission_allowed": False,
        "paper_order_submission_allowed": False,
        "live_execution_allowed": False,
        "automatic_promotion_allowed": False,
        **extra,
    }


def evaluate_runtime_shadow(
    readiness_proof,
    market_data_proof,
    intent,
    now=None,
    max_readiness_age_seconds=DEFAULT_MAX_READINESS_AGE_SECONDS,
    engine=None,
    ledger_path=None,
):
    now = _utc_datetime(now) or datetime.now(timezone.utc)
    readiness_proof = readiness_proof or {}
    market_data_proof = market_data_proof or {}
    intent = intent or {}

    readiness_age = _age_seconds(
        readiness_proof.get("generated_at"),
        now,
    )
    if (
        readiness_proof.get("status")
        != "READY_FOR_CONTROLLED_DRY_RUN"
    ):
        return _block("G2_G3_READINESS_REQUIRED")

    if (
        readiness_age is None
        or readiness_age > float(max_readiness_age_seconds)
    ):
        return _block(
            "G2_G3_READINESS_STALE",
            readiness_age_seconds=readiness_age,
        )

    readiness_flags_safe = all(
        readiness_proof.get(name) is False
        for name in (
            "broker_submission_allowed",
            "paper_order_submission_allowed",
            "live_execution_allowed",
            "automatic_promotion_allowed",
        )
    )
    if not readiness_flags_safe:
        return _block("READINESS_SUBMISSION_FLAGS_NOT_SAFE")

    market_flags_safe = all(
        market_data_proof.get(name) is False
        for name in (
            "broker_submission_allowed",
            "paper_order_submission_allowed",
            "live_execution_allowed",
        )
    )
    if not market_flags_safe:
        return _block("MARKET_PROOF_SUBMISSION_FLAGS_NOT_SAFE")

    snapshot = market_data_proof.get("snapshot") or {}
    quote = snapshot.get("quote") or {}
    proof_symbol = str(
        market_data_proof.get("symbol") or ""
    ).strip().upper()
    intent_symbol = str(intent.get("symbol") or "").strip().upper()

    if snapshot.get("status") != "REALTIME_READY" or not quote:
        return _block("VERIFIED_REALTIME_QUOTE_REQUIRED")

    if not proof_symbol or intent_symbol != proof_symbol:
        return _block(
            "INTENT_MARKET_SYMBOL_MISMATCH",
            intent_symbol=intent_symbol or None,
            market_symbol=proof_symbol or None,
        )

    if os.getenv("AURORA_RUN_MODE", "").strip().upper() != "DRY_RUN":
        return _block("DRY_RUN_MODE_REQUIRED")

    shadow_engine = engine or DryRunExecutionEngine()
    shadow_order = shadow_engine.evaluate_and_create_shadow_order(
        intent,
        quote,
    )
    if shadow_order.get("status") != "SHADOW_ACCEPTED":
        return _block(
            shadow_order.get("reason", "SHADOW_GATE_BLOCKED"),
            readiness_age_seconds=readiness_age,
            readiness_proof_sha256=_digest(readiness_proof),
            market_data_proof_sha256=_digest(market_data_proof),
            shadow_gate=shadow_order,
        )

    ledger_receipt = None
    if ledger_path is not None:
        try:
            ledger_receipt = ShadowAuditLedger(
                ledger_path
            ).record_shadow_order(
                shadow_order,
                {
                    "readiness_proof_sha256": _digest(readiness_proof),
                    "market_data_proof_sha256": _digest(market_data_proof),
                },
            )
        except Exception as error:
            return _block(
                "PERSISTENT_SHADOW_LEDGER_UNAVAILABLE",
                error_type=type(error).__name__,
            )

        if ledger_receipt.get("recorded") is not True:
            return _block(
                "PERSISTENT_DUPLICATE_ORDER_INTENT",
                ledger_receipt=ledger_receipt,
            )

    return {
        "engine": "AURORA V8.9.17 G4 Runtime Shadow Gate",
        "generated_at": now.isoformat(),
        "status": "SHADOW_ACCEPTED",
        "symbol": intent_symbol,
        "readiness_age_seconds": readiness_age,
        "readiness_proof_sha256": _digest(readiness_proof),
        "market_data_proof_sha256": _digest(market_data_proof),
        "shadow_order": shadow_order,
        "ledger_receipt": ledger_receipt,
        "broker_submission_allowed": False,
        "paper_order_submission_allowed": False,
        "live_execution_allowed": False,
        "automatic_promotion_allowed": False,
        "next_milestone": "G4_OPERATOR_REVIEW",
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
    parser.add_argument("--intent", required=True)
    parser.add_argument("--readiness-proof", default=DEFAULT_READINESS_PROOF)
    parser.add_argument(
        "--market-data-proof",
        default=DEFAULT_MARKET_DATA_PROOF,
    )
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument("--ledger", default=DEFAULT_LEDGER)
    args = parser.parse_args(argv)

    result = evaluate_runtime_shadow(
        _read_json(args.readiness_proof),
        _read_json(args.market_data_proof),
        _read_json(args.intent),
        ledger_path=args.ledger,
    )
    _write_atomic(args.output, result)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("status") == "SHADOW_ACCEPTED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
