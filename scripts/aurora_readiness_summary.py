#!/usr/bin/env python3
"""Bind fresh G0-G3 runtime evidence without authorizing any order."""

from datetime import datetime, timezone
import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile
import sys
from uuid import UUID


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from engines.gateway_readonly_attestation_verifier import (
    verify_installed_gateway_readonly_attestation,
)


DEFAULT_G0_PROOF = "runtime/gcp/latest.json"
DEFAULT_G2_PROOF = "runtime/ibkr_paper_read_only/latest.json"
DEFAULT_G3_PROOF = "runtime/ibkr_market_data/latest.json"
DEFAULT_OUTPUT = "runtime/aurora_readiness/latest.json"
DEFAULT_MAX_G2_AGE_SECONDS = 300
DEFAULT_MAX_G3_AGE_SECONDS = 60
DEFAULT_MAX_G0_AGE_SECONDS = 86400

EXPECTED_G2_REQUIRED_CHECKS = {
    "paper_mode_only",
    "safe_loopback_paper_endpoint",
    "paper_account_allowlist_configured",
    "paper_account_identity_verified",
    "verified_account_fingerprint_payload_valid",
    "account_summary_accounts_match_managed_accounts",
    "connector_read_only",
    "gateway_read_only_configuration_independently_attested",
    "order_submission_hard_blocked",
    "broker_mutation_surface_hard_blocked",
    "nonbinding_open_order_observation",
    "nonzero_api_client_id",
    "live_trading_hard_blocked",
    "official_ibapi_available",
    "gateway_connected",
    "managed_account_identity_consistent",
    "managed_account_received",
    "single_managed_account_for_readiness",
    "net_liquidation_available",
    "cash_available",
    "available_funds_available",
    "managed_accounts_snapshot_complete",
    "account_summary_snapshot_complete",
    "positions_snapshot_complete",
    "open_orders_snapshot_complete",
    "open_orders_payload_valid",
    "open_order_accounts_match_verified_paper_accounts",
    "positions_payload_valid",
    "position_accounts_match_verified_paper_accounts",
}


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


def _verified_account_fingerprints(account_guard):
    values = account_guard.get("verified_account_fingerprints")
    if not isinstance(values, list):
        return ()
    fingerprints = tuple(str(value).strip() for value in values)
    canonical = tuple(sorted(set(fingerprints)))
    if not fingerprints or fingerprints != canonical:
        return ()
    if any(
        len(value) != 15
        or not value.startswith("IBKR-")
        or any(character not in "0123456789ABCDEF" for character in value[5:])
        for value in fingerprints
    ):
        return ()
    return fingerprints


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


def evaluate_readiness_bundle(
    g2_proof,
    g3_proof,
    now=None,
    max_g2_age_seconds=DEFAULT_MAX_G2_AGE_SECONDS,
    max_g3_age_seconds=DEFAULT_MAX_G3_AGE_SECONDS,
    g0_proof=None,
    max_g0_age_seconds=DEFAULT_MAX_G0_AGE_SECONDS,
    gateway_attestation_verification=None,
):
    now = _utc_datetime(now) or datetime.now(timezone.utc)
    g2_proof = g2_proof or {}
    g3_proof = g3_proof or {}
    g0_proof = g0_proof or {}
    gateway_attestation_verification = (
        gateway_attestation_verification
        if isinstance(
            gateway_attestation_verification,
            dict,
        )
        else {}
    )

    g2_run_mode = g2_proof.get("run_mode") or {}
    g2_readiness = g2_proof.get("readiness") or {}
    g2_snapshot = g2_proof.get("snapshot") or {}
    g2_gateway_attestation = (
        g2_proof.get("gateway_read_only_attestation")
        if isinstance(
            g2_proof.get("gateway_read_only_attestation"),
            dict,
        )
        else {}
    )
    g2_account_guard = g2_snapshot.get("paper_account_guard") or {}
    g3_snapshot = g3_proof.get("snapshot") or {}
    g3_config = g3_snapshot.get("config") or {}
    g3_account_guard = g3_snapshot.get("paper_account_guard") or {}
    g3_quote = g3_snapshot.get("quote") or {}
    g3_market_gate = g3_proof.get("execution_market_data_gate") or {}
    g2_evidence_run_id = _verified_evidence_run_id(
        g2_proof.get("evidence_run_id")
    )
    g3_evidence_run_id = _verified_evidence_run_id(
        g3_proof.get("evidence_run_id")
    )
    g2_account_fingerprints = _verified_account_fingerprints(
        g2_account_guard
    )

    g2_checks = g2_readiness.get("checks")
    g2_checks_well_formed = (
        isinstance(g2_checks, list)
        and bool(g2_checks)
        and all(
            isinstance(item, dict)
            and isinstance(item.get("check"), str)
            and item.get("check")
            and isinstance(item.get("required"), bool)
            and isinstance(item.get("passed"), bool)
            for item in g2_checks
        )
    )
    g2_check_names = (
        [
            item["check"]
            for item in g2_checks
        ]
        if g2_checks_well_formed
        else []
    )
    g2_checks_unique = (
        bool(
            g2_check_names
        )
        and len(
            g2_check_names
        )
        ==
        len(
            set(
                g2_check_names
            )
        )
    )
    g2_required_check_names = (
        {
            item["check"]
            for item in g2_checks
            if item.get("required") is True
        }
        if g2_checks_well_formed
        else set()
    )
    g2_computed_required_failures = (
        sum(
            1
            for item in g2_checks
            if item.get("required") is True
            and item.get("passed") is not True
        )
        if g2_checks_well_formed
        else None
    )

    g3_account_fingerprints = _verified_account_fingerprints(
        g3_account_guard
    )

    g0_proof_sha256 = _digest(g0_proof)
    g0_instance_id = str(
        g0_proof.get("gce_instance_id") or ""
    ).strip()
    g2_attested_instance_id = str(
        g2_gateway_attestation.get("gcp_instance_id") or ""
    ).strip()
    runtime_attested_instance_id = str(
        gateway_attestation_verification.get("gcp_instance_id") or ""
    ).strip()

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
            == g0_proof_sha256
            and gateway_attestation_verification.get(
                "g0_runtime_proof_sha256"
            )
            == g0_proof_sha256
        ),
        "g2_read_only_mode": g2_run_mode.get("mode") == "READ_ONLY",
        "g2_ready": g2_readiness.get("readiness") == "READY_FOR_PAPER_READ_ONLY",
        "g2_no_required_failures": g2_readiness.get("required_failure_count") == 0,
        "g2_required_checks_consistent": (
            g2_checks_well_formed
            and g2_checks_unique
            and g2_required_check_names
            ==
            EXPECTED_G2_REQUIRED_CHECKS
            and g2_computed_required_failures
            == g2_readiness.get("required_failure_count")
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
        "g2_signed_gateway_attestation_verified": (
            g2_gateway_attestation.get("status") == "VERIFIED"
            and g2_gateway_attestation.get("verified") is True
            and g2_gateway_attestation.get(
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
        "g2_gateway_attestation_runtime_bound": (
            bool(g2_gateway_attestation)
            and bool(gateway_attestation_verification)
            and _digest(g2_gateway_attestation)
            ==
            _digest(gateway_attestation_verification)
        ),
        "g2_order_submission_blocked": (
            g2_readiness.get("paper_order_submission_allowed") is False
            and g2_readiness.get("live_execution_allowed") is False
            and g2_snapshot.get("order_submission_hard_blocked") is True
            and g2_snapshot.get(
                "broker_mutation_surface_hard_blocked"
            )
            is True
            and g2_snapshot.get(
                "open_order_observation_mode"
            )
            ==
            "REQ_ALL_OPEN_ORDERS_NON_BINDING"
            and g2_snapshot.get(
                "client_zero_binding_hard_blocked"
            )
            is True
        ),
        "g2_evidence_fresh": (
            g2_age is not None
            and g2_age <= float(max_g2_age_seconds)
        ),
        "g2_g3_same_evidence_run": (
            g2_evidence_run_id is not None
            and g2_evidence_run_id == g3_evidence_run_id
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
        "g2_g3_paper_account_bound": (
            g2_account_guard.get("paper_account_verified") is True
            and g3_account_guard.get("paper_account_verified") is True
            and bool(g2_account_fingerprints)
            and g2_account_fingerprints == g3_account_fingerprints
        ),
        "g3_realtime_quote": (
            g3_quote.get("source") == "IBKR_REALTIME"
            and g3_quote.get("market_data_type_name") == "REALTIME"
            and g3_quote.get("execution_eligible") is True
            and g3_quote.get("broker_market_timestamp_verified") is True
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
        "engine": "AURORA V8.9.28 G0-G3 Runtime Readiness Bundle",
        "generated_at": now.isoformat(),
        "status": "READY_FOR_CONTROLLED_DRY_RUN" if ready else "NOT_READY",
        "checks": checks,
        "failure_reasons": failures,
        "g0_g1_evidence_age_seconds": g0_age,
        "g2_evidence_age_seconds": g2_age,
        "g3_evidence_age_seconds": g3_age,
        "symbol": g3_proof.get("symbol"),
        "evidence_run_id": (
            g2_evidence_run_id
            if checks["g2_g3_same_evidence_run"]
            else None
        ),
        "g0_g1_proof_sha256": g0_proof_sha256,
        "gce_instance_id": (
            g0_instance_id
            if checks[
                "g0_control_plane_instance_bound_to_gateway_attestation"
            ]
            else None
        ),
        "g2_paper_read_only_proof_sha256": _digest(g2_proof),
        "g3_market_data_proof_sha256": _digest(g3_proof),
        "gateway_read_only_attestation_sha256": (
            _digest(gateway_attestation_verification)
            if checks["g2_signed_gateway_attestation_verified"]
            and checks["gateway_attestation_runtime_verified"]
            and checks["g2_gateway_attestation_runtime_bound"]
            else None
        ),
        "paper_account_fingerprints": (
            list(g2_account_fingerprints)
            if checks["g2_g3_paper_account_bound"]
            else []
        ),
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

    gateway_attestation_verification = (
        verify_installed_gateway_readonly_attestation(
            REPOSITORY_ROOT
        )
    )

    result = evaluate_readiness_bundle(
        _read_json(args.g2_proof),
        _read_json(args.g3_proof),
        g0_proof=_read_json(args.g0_proof),
        gateway_attestation_verification=(
            gateway_attestation_verification
        ),
    )
    _write_atomic(args.output, result)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "READY_FOR_CONTROLLED_DRY_RUN" else 2


if __name__ == "__main__":
    raise SystemExit(main())
