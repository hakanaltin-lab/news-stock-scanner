#!/usr/bin/env python3
"""Fail-closed G0-G4 completion status for the Paper shadow milestone."""

import argparse
from datetime import datetime, timezone
import hashlib
import hmac
import json
import os
from pathlib import Path
import sys
from uuid import UUID


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from engines.shadow_audit_verifier import receipt_binding_sha256
from engines.gateway_readonly_attestation_verifier import (
    verify_installed_gateway_readonly_attestation,
)
from scripts.gateway_review_package import (
    read_trusted_runtime_evidence_json,
)
from scripts.ibkr_paper_probe import (
    write_runtime_evidence_atomic,
)


DEFAULT_G0_PROOF = "runtime/gcp/latest.json"
DEFAULT_G2_PROOF = "runtime/ibkr_paper_read_only/latest.json"
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


def _verified_evidence_run_id(value):
    text = str(value or "").strip()
    try:
        parsed = UUID(text)
    except (ValueError, AttributeError):
        return None
    canonical = str(parsed)
    if parsed.version != 4 or text != canonical:
        return None
    return canonical


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


def _flags_safe(
    payload,
    include_automatic=True,
    include_real_money=False,
):
    names = [
        "broker_submission_allowed",
        "paper_order_submission_allowed",
        "live_execution_allowed",
    ]
    if include_automatic:
        names.append("automatic_promotion_allowed")
    if include_real_money:
        names.append("real_money_trading_allowed")
    return all(
        name in payload
        and payload.get(name) is False
        for name in names
    )


def _shadow_flags_safe(payload):
    names = (
        "broker_submission_allowed",
        "paper_order_submission_allowed",
        "live_execution_allowed",
        "automatic_promotion_allowed",
        "real_money_trading_allowed",
    )
    return (
        isinstance(payload, dict)
        and all(
            name in payload
            and payload.get(name) is False
            for name in names
        )
    )


def evaluate_completion_status(
    g0_proof,
    readiness,
    g4_shadow,
    ledger_audit,
    now=None,
    g2_proof=None,
    gateway_attestation_verification=None,
):
    now = _utc_datetime(now) or datetime.now(timezone.utc)
    g0_proof = g0_proof or {}
    readiness = readiness or {}
    g4_shadow = g4_shadow or {}
    ledger_audit = ledger_audit or {}
    g2_proof = g2_proof or {}
    gateway_attestation_verification = (
        gateway_attestation_verification
        if isinstance(
            gateway_attestation_verification,
            dict,
        )
        else {}
    )

    ages = {
        "g0_seconds": _age_seconds(g0_proof.get("generated_at"), now),
        "readiness_seconds": _age_seconds(readiness.get("generated_at"), now),
        "g4_seconds": _age_seconds(g4_shadow.get("generated_at"), now),
        "ledger_audit_seconds": _age_seconds(
            ledger_audit.get("generated_at"), now
        ),
    }
    receipt = g4_shadow.get("ledger_receipt") or {}
    actual_receipt_digest = receipt_binding_sha256(receipt)

    g4_shadow_order = (
        g4_shadow.get("shadow_order")
        if isinstance(
            g4_shadow.get("shadow_order"),
            dict,
        )
        else {}
    )
    actual_g4_shadow_order_digest = (
        _digest(g4_shadow_order)
        if g4_shadow_order
        else None
    )
    g4_market_digest = str(
        g4_shadow.get("market_data_proof_sha256") or ""
    ).strip().lower()
    g4_ledger_evidence = {
        "evidence_run_id": g4_shadow.get("evidence_run_id"),
        "readiness_proof_sha256": str(
            g4_shadow.get("readiness_proof_sha256") or ""
        ).strip().lower(),
        "market_data_proof_sha256": g4_market_digest,
    }
    receipt_recorded_at = receipt.get("recorded_at")
    expected_g4_ledger_payload_digest = (
        _digest({
            "shadow_order": g4_shadow_order,
            "evidence": g4_ledger_evidence,
            "recorded_at": receipt_recorded_at,
        })
        if g4_shadow_order
        and isinstance(receipt_recorded_at, str)
        and receipt_recorded_at.strip()
        else None
    )
    receipt_payload_digest = str(
        receipt.get("payload_sha256") or ""
    ).strip().lower()
    audited_receipt_digest = str(
        ledger_audit.get("expected_receipt_sha256") or ""
    ).strip().lower()
    actual_readiness_digest = _digest(readiness)
    actual_g0_digest = _digest(g0_proof)
    actual_g2_digest = _digest(g2_proof)
    g2_gateway_attestation = (
        g2_proof.get("gateway_read_only_attestation")
        if isinstance(
            g2_proof.get("gateway_read_only_attestation"),
            dict,
        )
        else {}
    )
    actual_g2_gateway_attestation_digest = (
        _digest(g2_gateway_attestation)
        if g2_gateway_attestation
        else None
    )
    actual_runtime_gateway_attestation_digest = (
        _digest(gateway_attestation_verification)
        if gateway_attestation_verification
        else None
    )
    readiness_gateway_attestation_digest = str(
        readiness.get("gateway_read_only_attestation_sha256") or ""
    ).strip().lower()
    readiness_g0_digest = str(
        readiness.get("g0_g1_proof_sha256") or ""
    ).strip().lower()
    readiness_g2_digest = str(
        readiness.get("g2_paper_read_only_proof_sha256") or ""
    ).strip().lower()
    recorded_readiness_digest = str(
        g4_shadow.get("readiness_proof_sha256") or ""
    ).strip().lower()
    readiness_run_id = _verified_evidence_run_id(
        readiness.get("evidence_run_id")
    )
    g4_run_id = _verified_evidence_run_id(
        g4_shadow.get("evidence_run_id")
    )
    g2_snapshot = (
        g2_proof.get("snapshot")
        if isinstance(
            g2_proof.get("snapshot"),
            dict,
        )
        else {}
    )
    g2_readiness = (
        g2_proof.get("readiness")
        if isinstance(
            g2_proof.get("readiness"),
            dict,
        )
        else {}
    )
    g0_instance_id = str(
        g0_proof.get("gce_instance_id") or ""
    ).strip()
    g2_attested_instance_id = str(
        g2_gateway_attestation.get("gcp_instance_id") or ""
    ).strip()
    runtime_attested_instance_id = str(
        gateway_attestation_verification.get("gcp_instance_id") or ""
    ).strip()

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
        "g0_control_plane_instance_bound_to_gateway_attestation": (
            bool(g0_instance_id)
            and g0_instance_id.isdigit()
            and g0_instance_id == g2_attested_instance_id
            == runtime_attested_instance_id
        ),
        "g0_signed_proof_digest_bound": (
            g2_gateway_attestation.get(
                "g0_runtime_proof_sha256"
            )
            == actual_g0_digest
            and gateway_attestation_verification.get(
                "g0_runtime_proof_sha256"
            )
            == actual_g0_digest
        ),
        "g2_g3_ready": (
            readiness.get("status") == "READY_FOR_CONTROLLED_DRY_RUN"
            and not readiness.get("failure_reasons")
            and _flags_safe(
                readiness,
                include_real_money=True,
            )
        ),
        "g2_post_review_probe_stage": (
            g2_proof.get("probe_stage") == "POST_REVIEW_PROBE"
            and readiness.get("g2_probe_stage") == "POST_REVIEW_PROBE"
        ),
        "g0_g1_readiness_proof_bound": (
            _is_sha256(readiness_g0_digest)
            and hmac.compare_digest(
                readiness_g0_digest,
                actual_g0_digest,
            )
        ),
        "g2_gateway_read_only_independently_attested": (
            g2_snapshot.get(
                "gateway_read_only_configuration_independently_attested"
            )
            is True
            and g2_readiness.get(
                "gateway_read_only_configuration_independently_attested"
            )
            is True
        ),
        "gateway_attestation_runtime_verified": (
            gateway_attestation_verification.get("status") == "VERIFIED"
            and gateway_attestation_verification.get("verified") is True
            and gateway_attestation_verification.get(
                "gateway_read_only_configuration_independently_attested"
            )
            is True
        ),
        "gateway_attestation_g2_runtime_bound": (
            bool(g2_gateway_attestation)
            and actual_g2_gateway_attestation_digest
            is not None
            and actual_runtime_gateway_attestation_digest
            is not None
            and hmac.compare_digest(
                actual_g2_gateway_attestation_digest,
                actual_runtime_gateway_attestation_digest,
            )
        ),
        "gateway_attestation_readiness_bound": (
            _is_sha256(
                readiness_gateway_attestation_digest
            )
            and actual_runtime_gateway_attestation_digest
            is not None
            and hmac.compare_digest(
                readiness_gateway_attestation_digest,
                actual_runtime_gateway_attestation_digest,
            )
        ),
        "g2_readiness_proof_bound": (
            _is_sha256(readiness_g2_digest)
            and hmac.compare_digest(
                readiness_g2_digest,
                actual_g2_digest,
            )
        ),
        "g2_g3_evidence_fresh": (
            ages["readiness_seconds"] is not None
            and ages["readiness_seconds"] <= 120
        ),
        "g4_shadow_accepted": (
            g4_shadow.get("status") == "SHADOW_ACCEPTED"
            and _flags_safe(
                g4_shadow,
                include_real_money=True,
            )
            and receipt.get("recorded") is True
            and receipt.get("duplicate") is False
        ),
        "g4_shadow_order_payload_valid": (
            bool(g4_shadow_order)
            and g4_shadow_order.get("status") == "SHADOW_ACCEPTED"
            and _shadow_flags_safe(g4_shadow_order)
            and bool(
                str(
                    g4_shadow_order.get("shadow_order_id") or ""
                ).strip()
            )
            and bool(
                str(
                    g4_shadow_order.get("idempotency_key") or ""
                ).strip()
            )
            and bool(
                str(
                    g4_shadow_order.get("symbol") or ""
                ).strip()
            )
        ),
        "g4_shadow_order_ledger_payload_bound": (
            actual_g4_shadow_order_digest is not None
            and expected_g4_ledger_payload_digest is not None
            and _is_sha256(receipt_payload_digest)
            and hmac.compare_digest(
                receipt_payload_digest,
                expected_g4_ledger_payload_digest,
            )
            and receipt.get("shadow_order_id")
            == g4_shadow_order.get("shadow_order_id")
            and receipt.get("idempotency_key")
            == g4_shadow_order.get("idempotency_key")
            and str(receipt.get("symbol") or "").strip().upper()
            == str(g4_shadow_order.get("symbol") or "").strip().upper()
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
        "g4_evidence_run_bound": (
            readiness_run_id is not None
            and readiness_run_id == g4_run_id
        ),
        "shadow_ledger_verified": (
            ledger_audit.get("status") == "LEDGER_VERIFIED"
            and not ledger_audit.get("failure_reasons")
            and (ledger_audit.get("record_count") or 0) >= 1
            and _flags_safe(
                ledger_audit,
                include_real_money=True,
            )
        ),
        "g4_ledger_receipt_bound": (
            actual_receipt_digest is not None
            and ledger_audit.get("expected_receipt_bound") is True
            and _is_sha256(audited_receipt_digest)
            and hmac.compare_digest(
                actual_receipt_digest,
                audited_receipt_digest,
            )
        ),
        "ledger_audit_fresh": (
            ages["ledger_audit_seconds"] is not None
            and ages["ledger_audit_seconds"] <= 60
        ),
    }
    failures = [name for name, passed in checks.items() if not passed]
    complete = not failures
    return {
        "engine": "AURORA V8.9.29 G0-G4 Completion Gate",
        "generated_at": now.isoformat(),
        "status": (
            "PAPER_RUNTIME_VALIDATED_SHADOW_ONLY"
            if complete
            else "BLOCKED"
        ),
        "checks": checks,
        "evidence_age": ages,
        "evidence_binding": {
            "readiness_evidence_run_id": readiness_run_id,
            "g4_evidence_run_id": g4_run_id,
            "g0_g1_proof_sha256": actual_g0_digest,
            "gce_instance_id": (
                g0_instance_id
                if checks[
                    "g0_control_plane_instance_bound_to_gateway_attestation"
                ]
                else None
            ),
            "readiness_recorded_g0_g1_proof_sha256": (
                readiness_g0_digest or None
            ),
            "g2_paper_read_only_proof_sha256": actual_g2_digest,
            "readiness_recorded_g2_proof_sha256": (
                readiness_g2_digest or None
            ),
            "g2_gateway_read_only_attestation_sha256": (
                actual_g2_gateway_attestation_digest
            ),
            "runtime_gateway_read_only_attestation_sha256": (
                actual_runtime_gateway_attestation_digest
            ),
            "readiness_recorded_gateway_attestation_sha256": (
                readiness_gateway_attestation_digest or None
            ),
            "readiness_proof_sha256": actual_readiness_digest,
            "g4_recorded_readiness_proof_sha256": (
                recorded_readiness_digest or None
            ),
            "g4_shadow_order_sha256": (
                actual_g4_shadow_order_digest
            ),
            "g4_ledger_payload_sha256": (
                receipt_payload_digest or None
            ),
            "g4_recomputed_ledger_payload_sha256": (
                expected_g4_ledger_payload_digest
            ),
            "g4_ledger_receipt_sha256": actual_receipt_digest,
            "audited_ledger_receipt_sha256": (
                audited_receipt_digest or None
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


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--g0-proof", default=DEFAULT_G0_PROOF)
    parser.add_argument("--g2-proof", default=DEFAULT_G2_PROOF)
    parser.add_argument("--readiness", default=DEFAULT_READINESS)
    parser.add_argument("--g4-shadow", default=DEFAULT_G4_SHADOW)
    parser.add_argument("--ledger-audit", default=DEFAULT_LEDGER_AUDIT)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    gateway_attestation_verification = (
        verify_installed_gateway_readonly_attestation(
            REPOSITORY_ROOT
        )
    )

    result = evaluate_completion_status(
        _read_json(args.g0_proof),
        read_trusted_runtime_evidence_json(
            args.readiness
        ),
        read_trusted_runtime_evidence_json(
            args.g4_shadow
        ),
        read_trusted_runtime_evidence_json(
            args.ledger_audit
        ),
        g2_proof=read_trusted_runtime_evidence_json(
            args.g2_proof
        ),
        gateway_attestation_verification=(
            gateway_attestation_verification
        ),
    )
    try:
        write_runtime_evidence_atomic(
            args.output,
            result,
        )
    except (
        OSError,
        RuntimeError,
        ValueError,
    ):
        print(json.dumps({
            "status": "RUNTIME_EVIDENCE_WRITE_FAILED",
            "broker_submission_allowed": False,
            "paper_order_submission_allowed": False,
            "live_execution_allowed": False,
            "automatic_promotion_allowed": False,
            "real_money_trading_allowed": False,
        }, indent=2, sort_keys=True))
        return 2

    print(json.dumps(result, indent=2, sort_keys=True))
    return (
        0
        if result.get("status") == "PAPER_RUNTIME_VALIDATED_SHADOW_ONLY"
        else 2
    )


if __name__ == "__main__":
    raise SystemExit(main())
