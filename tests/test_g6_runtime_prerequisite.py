"""G8.12 safety tests for the G6 runtime prerequisite review gate."""

from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch

from engines.ibkr_paper_readiness_engine import (
    evaluate_ibkr_paper_readiness,
)
from engines.paper_connector_review_prerequisite import (
    evaluate_g6_runtime_prerequisite,
)
from engines.paper_order_authorization_gate import (
    AUTH_VERSION,
    REQUIRED_COMPLETION_CHECKS,
    evaluate_manual_paper_authorization,
)
from scripts import g6_runtime_prerequisite as cli


NOW = datetime(2026, 11, 2, 13, 40, tzinfo=timezone.utc)
EVIDENCE_RUN_ID = "11111111-1111-4111-8111-111111111111"
INSTANCE_ID = "1234567890123456789"
GIT_SHA = "a" * 40
G0_DIGEST = "b" * 64
ACCOUNT = "IBKR-A1B2C3D4E5"


def digest(payload):
    return hashlib.sha256(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def safe_flags():
    return {
        "broker_submission_allowed": False,
        "paper_order_submission_allowed": False,
        "live_execution_allowed": False,
        "automatic_promotion_allowed": False,
        "real_money_trading_allowed": False,
    }


def gateway_attestation():
    return {
        "engine": "AURORA G7.5 Gateway Read-Only Attestation Verifier",
        "status": "VERIFIED",
        "verified": True,
        "gateway_read_only_configuration_independently_attested": True,
        "failure_reasons": [],
        "attestation_id": "22222222-2222-4222-8222-222222222222",
        "reviewer_id": "aurora-independent-reviewer",
        "captured_at_utc": (NOW - timedelta(minutes=1)).isoformat(),
        "expires_at_utc": (NOW + timedelta(hours=1)).isoformat(),
        "git_sha": GIT_SHA,
        "evidence_sha256": "c" * 64,
        "g0_runtime_proof_sha256": G0_DIGEST,
        "gcp_project_id": "project-ce9773ef-6814-469c-92b",
        "gcp_instance_id": INSTANCE_ID,
        **safe_flags(),
    }


def broker_snapshot():
    return {
        "timestamp": (NOW - timedelta(seconds=10)).isoformat(),
        "status": "CONNECTED",
        "connection_status": "CONNECTED",
        "config": {
            "enabled": True,
            "mode": "PAPER",
            "mode_valid": True,
            "host": "127.0.0.1",
            "port": 4002,
            "port_valid": True,
            "endpoint_safe": True,
            "read_only": True,
            "client_id": 82,
            "client_id_valid": True,
        },
        "official_ibapi_available": True,
        "order_submission_hard_blocked": True,
        "broker_mutation_surface_hard_blocked": True,
        "open_order_observation_mode": (
            "REQ_ALL_OPEN_ORDERS_NON_BINDING"
        ),
        "client_zero_binding_hard_blocked": True,
        "gateway_read_only_configuration_independently_attested": True,
        "live_trading_allowed": False,
        "account_count": 1,
        "accounts": [ACCOUNT],
        "paper_account_guard": {
            "allowlist_configured": True,
            "managed_account_received": True,
            "account_count": 1,
            "all_accounts_allowlisted": True,
            "paper_account_verified": True,
            "verified_account_fingerprints": [ACCOUNT],
            "reason": "PAPER_ACCOUNT_VERIFIED",
        },
        "account_summary_account_fingerprints": [ACCOUNT],
        "account_summary": {
            "NetLiquidation": {
                "value": 100000.0,
                "currency": "USD",
            },
            "TotalCashValue": {
                "value": 50000.0,
                "currency": "USD",
            },
            "AvailableFunds": {
                "value": 45000.0,
                "currency": "USD",
            },
            "BuyingPower": {
                "value": 180000.0,
                "currency": "USD",
            },
        },
        "positions": [],
        "open_orders": [],
        "requests_complete": {
            "managed_accounts": True,
            "account_summary": True,
            "positions": True,
            "open_orders": True,
        },
    }


def g2_proof():
    snapshot = broker_snapshot()
    readiness = evaluate_ibkr_paper_readiness(
        snapshot,
        [],
    )
    readiness["timestamp"] = (
        NOW - timedelta(seconds=10)
    ).isoformat()

    return {
        "git_sha": GIT_SHA,
        "evidence_run_id": EVIDENCE_RUN_ID,
        "run_mode": {
            "mode": "READ_ONLY",
            "live_execution_allowed": False,
            "paper_order_submission_requested": False,
        },
        "runtime_provenance": {
            "verified": True,
            "runtime_cloud_identity": {
                "project_id": "project-ce9773ef-6814-469c-92b",
                "instance_name": "aurora-trading-vps",
                "zone": "europe-west3-a",
                "instance_id": INSTANCE_ID,
            },
            "g0_runtime_proof_sha256": G0_DIGEST,
            "failure_reasons": [],
            **safe_flags(),
        },
        "snapshot": snapshot,
        "gateway_read_only_attestation": gateway_attestation(),
        "readiness": readiness,
    }


def shadow_order():
    return {
        "status": "SHADOW_ACCEPTED",
        "shadow_order_id": "shadow-g8-12-001",
        "idempotency_key": "intent-g8-12-001",
        "symbol": "BKR",
        "action": "BUY",
        "quantity": 1,
        "limit_price": 50.0,
        **safe_flags(),
    }


def g4_shadow(order=None):
    return {
        "status": "SHADOW_ACCEPTED",
        "shadow_order": order or shadow_order(),
        **safe_flags(),
    }


def completion(g2, order=None):
    order = order or shadow_order()
    attestation_digest = digest(
        g2["gateway_read_only_attestation"]
    )
    return {
        "engine": "AURORA V8.9.29 G0-G4 Completion Gate",
        "status": "PAPER_RUNTIME_VALIDATED_SHADOW_ONLY",
        "next_gate": "MANUAL_PAPER_ORDER_AUTHORIZATION_NOT_GRANTED",
        "checks": {
            name: True
            for name in REQUIRED_COMPLETION_CHECKS
        },
        "evidence_binding": {
            "readiness_evidence_run_id": EVIDENCE_RUN_ID,
            "g4_evidence_run_id": EVIDENCE_RUN_ID,
            "g0_g1_proof_sha256": G0_DIGEST,
            "gce_instance_id": INSTANCE_ID,
            "readiness_recorded_g0_g1_proof_sha256": G0_DIGEST,
            "g2_paper_read_only_proof_sha256": digest(g2),
            "readiness_recorded_g2_proof_sha256": digest(g2),
            "g2_gateway_read_only_attestation_sha256": attestation_digest,
            "runtime_gateway_read_only_attestation_sha256": attestation_digest,
            "readiness_recorded_gateway_attestation_sha256": attestation_digest,
            "readiness_proof_sha256": "d" * 64,
            "g4_recorded_readiness_proof_sha256": "d" * 64,
            "g4_shadow_order_sha256": digest(order),
            "g4_ledger_payload_sha256": "e" * 64,
            "g4_recomputed_ledger_payload_sha256": "e" * 64,
            "g4_ledger_receipt_sha256": "f" * 64,
            "audited_ledger_receipt_sha256": "f" * 64,
        },
        "failure_reasons": [],
        **safe_flags(),
    }


def authorization(comp, order=None):
    order = order or shadow_order()
    return {
        "version": AUTH_VERSION,
        "authorization_id": "33333333-3333-4333-8333-333333333333",
        "approved": True,
        "mode": "PAPER",
        "scope": "ONE_PAPER_ORDER",
        "issued_at": (NOW - timedelta(seconds=20)).isoformat(),
        "expires_at": (NOW + timedelta(minutes=5)).isoformat(),
        "completion_status_sha256": digest(comp),
        "shadow_order_sha256": digest(order),
        **safe_flags(),
    }


def full_chain():
    g2 = g2_proof()
    order = shadow_order()
    g4 = g4_shadow(order)
    comp = completion(g2, order)
    auth = authorization(comp, order)
    g5 = evaluate_manual_paper_authorization(
        comp,
        order,
        auth,
        now=NOW,
    )
    return g5, comp, g4, auth, g2, gateway_attestation()


def write_trusted(path, payload):
    path = Path(path)
    path.write_text(
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    path.chmod(0o600)


class G6RuntimePrerequisiteTests(unittest.TestCase):
    def evaluate(self):
        return evaluate_g6_runtime_prerequisite(
            *full_chain(),
            now=NOW,
        )

    def test_valid_chain_advances_only_to_source_review(self):
        result = self.evaluate()

        self.assertEqual(
            result["status"],
            "READY_FOR_PAPER_CONNECTOR_SOURCE_REVIEW",
        )
        self.assertEqual(
            result["next_gate"],
            "REBASE_AND_REVIEW_BROKER_ADAPTER_SOURCE_AGAINST_G8_12",
        )
        self.assertEqual(
            result["evidence_run_id"],
            EVIDENCE_RUN_ID,
        )
        self.assertEqual(result["git_sha"], GIT_SHA)
        self.assertEqual(
            result["gce_instance_id"],
            INSTANCE_ID,
        )
        self.assertEqual(
            result["paper_account_fingerprints"],
            [ACCOUNT],
        )
        for name in (
            "implementation_allowed",
            "connection_allowed",
            "broker_request_materialization_allowed",
            "broker_order_object_allowed",
            "automatic_retry_allowed",
            "automatic_cancel_allowed",
            "automatic_modify_allowed",
            "broker_submission_allowed",
            "paper_order_submission_allowed",
            "live_execution_allowed",
            "automatic_promotion_allowed",
            "real_money_trading_allowed",
        ):
            self.assertIs(result[name], False)

    def test_modified_g2_after_g5_validation_blocks(self):
        g5, comp, g4, auth, g2, attestation = full_chain()
        g2["snapshot"]["account_summary"][
            "TotalCashValue"
        ]["value"] = 49999.0

        result = evaluate_g6_runtime_prerequisite(
            g5,
            comp,
            g4,
            auth,
            g2,
            attestation,
            now=NOW,
        )

        self.assertEqual(result["status"], "BLOCKED")
        self.assertFalse(
            result["checks"]["g2_proof_digest_bound"]
        )

    def test_cross_vm_or_g0_provenance_blocks(self):
        g5, comp, g4, auth, g2, attestation = full_chain()
        g2["runtime_provenance"][
            "runtime_cloud_identity"
        ]["instance_id"] = "9876543210987654321"

        result = evaluate_g6_runtime_prerequisite(
            g5,
            comp,
            g4,
            auth,
            g2,
            attestation,
            now=NOW,
        )

        self.assertEqual(result["status"], "BLOCKED")
        self.assertFalse(
            result["checks"]["g2_runtime_provenance_bound"]
        )

    def test_changed_human_authorization_blocks(self):
        g5, comp, g4, auth, g2, attestation = full_chain()
        auth["authorization_id"] = (
            "44444444-4444-4444-8444-444444444444"
        )

        result = evaluate_g6_runtime_prerequisite(
            g5,
            comp,
            g4,
            auth,
            g2,
            attestation,
            now=NOW,
        )

        self.assertEqual(result["status"], "BLOCKED")
        self.assertFalse(
            result["checks"][
                "g5_recomputed_from_trusted_sources"
            ]
        )
        self.assertFalse(
            result["checks"][
                "g5_authorization_artifact_digest_valid"
            ]
        )

    def test_expired_human_authorization_blocks_revalidation(self):
        g5, comp, g4, auth, g2, attestation = full_chain()

        result = evaluate_g6_runtime_prerequisite(
            g5,
            comp,
            g4,
            auth,
            g2,
            attestation,
            now=NOW + timedelta(minutes=6),
        )

        self.assertEqual(result["status"], "BLOCKED")
        self.assertFalse(
            result["checks"][
                "g5_recomputed_from_trusted_sources"
            ]
        )

    def test_runtime_attestation_mismatch_blocks(self):
        g5, comp, g4, auth, g2, attestation = full_chain()
        attestation["evidence_sha256"] = "9" * 64

        result = evaluate_g6_runtime_prerequisite(
            g5,
            comp,
            g4,
            auth,
            g2,
            attestation,
            now=NOW,
        )

        self.assertEqual(result["status"], "BLOCKED")
        self.assertFalse(
            result["checks"][
                "gateway_attestation_exactly_bound"
            ]
        )

    def test_stale_g2_blocks(self):
        g5, comp, g4, auth, g2, attestation = full_chain()
        g2["readiness"]["timestamp"] = (
            NOW - timedelta(minutes=6)
        ).isoformat()

        result = evaluate_g6_runtime_prerequisite(
            g5,
            comp,
            g4,
            auth,
            g2,
            attestation,
            now=NOW,
        )

        self.assertEqual(result["status"], "BLOCKED")
        self.assertFalse(
            result["checks"]["g2_fresh"]
        )

    def test_cli_writes_trusted_review_only_output(self):
        g5, comp, g4, auth, g2, attestation = full_chain()

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = {}
            for name, payload in (
                ("g5", g5),
                ("completion", comp),
                ("g4", g4),
                ("authorization", auth),
                ("g2", g2),
            ):
                path = root / f"{name}.json"
                write_trusted(path, payload)
                paths[name] = path

            output = root / "g6-prerequisite.json"

            with patch.object(
                cli,
                "verify_installed_gateway_readonly_attestation",
                return_value=attestation,
            ), patch.object(
                cli,
                "evaluate_g6_runtime_prerequisite",
                side_effect=lambda *args, **kwargs: (
                    evaluate_g6_runtime_prerequisite(
                        *args,
                        now=NOW,
                        **kwargs,
                    )
                ),
            ):
                code = cli.main([
                    "--authorization",
                    str(paths["authorization"]),
                    "--g5-validation",
                    str(paths["g5"]),
                    "--completion-status",
                    str(paths["completion"]),
                    "--g4-shadow",
                    str(paths["g4"]),
                    "--g2-proof",
                    str(paths["g2"]),
                    "--output",
                    str(output),
                ])

            self.assertEqual(code, 0)
            payload = json.loads(
                output.read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(
                payload["status"],
                "READY_FOR_PAPER_CONNECTOR_SOURCE_REVIEW",
            )
            metadata = output.stat()
            self.assertTrue(
                stat.S_ISREG(metadata.st_mode)
            )
            self.assertEqual(
                stat.S_IMODE(metadata.st_mode),
                0o600,
            )
            self.assertEqual(metadata.st_nlink, 1)
            self.assertFalse(
                payload["connection_allowed"]
            )
            self.assertFalse(
                payload["paper_order_submission_allowed"]
            )


if __name__ == "__main__":
    unittest.main()
