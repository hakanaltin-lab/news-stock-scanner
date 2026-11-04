"""G7.11 tests for the non-attesting reviewer package builder."""

from datetime import datetime, timedelta, timezone
import inspect
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import gateway_review_package as review_package

from scripts.gateway_review_package import (
    PACKAGE_TYPE,
    RUNTIME_BOUND_PACKAGE_SCHEMA_VERSION,
    RUNTIME_BOUND_PACKAGE_TYPE,
    _REQUIRED_G2_PASSED_CHECKS,
    build_runtime_bound_review_package,
    build_unsigned_review_package,
)
from scripts.aurora_readiness_summary import (
    EXPECTED_G2_REQUIRED_CHECKS,
)
from engines.gateway_attestation_handoff import (
    HANDOFF_REQUEST_TYPE,
)
from engines.gateway_readonly_attestation_verifier import (
    ATTESTATION_TYPE,
    SIGNATURE_ALGORITHM,
    evaluate_gateway_readonly_attestation,
)


NOW = datetime(2026, 11, 2, 11, 30, tzinfo=timezone.utc)
GIT_SHA = "a" * 40
G0_SHA = "c" * 64
PROJECT_ID = "project-ce9773ef-6814-469c-92b"
INSTANCE_NAME = "aurora-trading-vps"
ZONE = "europe-west3-a"
INSTANCE_ID = "1234567890123456789"
REVIEWER = "aurora-independent-reviewer"
ACCOUNT_FINGERPRINT = "IBKR-A1B2C3D4E5"
EVIDENCE_RUN_ID = "11111111-1111-4111-8111-111111111111"


def g2_diagnostic(timestamp=None):
    timestamp = timestamp or (
        NOW - timedelta(seconds=10)
    ).isoformat()
    safe_permissions = {
        "broker_submission_allowed": False,
        "paper_order_submission_allowed": False,
        "live_execution_allowed": False,
        "automatic_promotion_allowed": False,
        "real_money_trading_allowed": False,
    }
    checks = [
        {
            "check": name,
            "required": True,
            "passed": True,
        }
        for name in sorted(_REQUIRED_G2_PASSED_CHECKS)
    ]
    checks.append({
        "check": (
            "gateway_read_only_configuration_independently_attested"
        ),
        "required": True,
        "passed": False,
    })
    return {
        "git_sha": GIT_SHA,
        "evidence_run_id": EVIDENCE_RUN_ID,
        "probe_stage": "PRE_REVIEW_DIAGNOSTIC",
        "run_mode": {
            "mode": "READ_ONLY",
            "live_execution_allowed": False,
        },
        "runtime_provenance": {
            "verified": True,
            "runtime_cloud_identity": {
                "project_id": PROJECT_ID,
                "instance_name": INSTANCE_NAME,
                "zone": ZONE,
                "instance_id": INSTANCE_ID,
            },
            "g0_runtime_proof_sha256": G0_SHA,
            "failure_reasons": [],
            **safe_permissions,
        },
        "snapshot": {
            "timestamp": timestamp,
            "status": "CONNECTED",
            "connection_status": "CONNECTED",
            "official_ibapi_available": True,
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
            "order_submission_hard_blocked": True,
            "broker_mutation_surface_hard_blocked": True,
            "client_zero_binding_hard_blocked": True,
            "open_order_observation_mode": (
                "REQ_ALL_OPEN_ORDERS_NON_BINDING"
            ),
            "blocked_broker_mutation_methods": [
                "placeOrder",
                "cancelOrder",
                "reqGlobalCancel",
                "exerciseOptions",
                "replaceFA",
                "reqAutoOpenOrders",
            ],
            "live_trading_allowed": False,
            "gateway_read_only_configuration_independently_attested": False,
            "accounts": [ACCOUNT_FINGERPRINT],
            "account_count": 1,
            "account_summary_account_fingerprints": [
                ACCOUNT_FINGERPRINT
            ],
            "paper_account_guard": {
                "allowlist_configured": True,
                "paper_account_verified": True,
                "account_count": 1,
                "verified_account_fingerprints": [
                    ACCOUNT_FINGERPRINT
                ],
            },
            "positions": [],
            "open_orders": [],
            "order_status": [],
            "executions": [],
            "requests_complete": {
                "managed_accounts": True,
                "account_summary": True,
                "positions": True,
                "open_orders": True,
                "executions": True,
            },
        },
        "gateway_read_only_attestation": {
            "status": "BLOCKED",
            "verified": False,
            "gateway_read_only_configuration_independently_attested": False,
            "failure_reasons": ["ATTESTATION_ARTIFACT_UNTRUSTED"],
            **safe_permissions,
        },
        "readiness": {
            "timestamp": timestamp,
            "readiness": "NOT_READY",
            "diagnostic_read_only_ready": True,
            "required_failure_count": 1,
            "checks": checks,
            "gateway_read_only_configuration_independently_attested": False,
            "paper_order_submission_allowed": False,
            "live_execution_allowed": False,
            "next_milestone": (
                "INDEPENDENT_GATEWAY_READ_ONLY_ATTESTATION"
            ),
        },
    }


def handoff_request():
    return {
        "request_schema_version": 3,
        "request_type": HANDOFF_REQUEST_TYPE,
        "requested_control": ATTESTATION_TYPE,
        "generated_at_utc": NOW.isoformat(),
        "git_sha": GIT_SHA,
        "instance_name": INSTANCE_NAME,
        "zone": ZONE,
        "broker_mode": "PAPER",
        "gateway_port": 4002,
        "reviewer_id": REVIEWER,
        "reviewer_public_key_sha256": "d" * 64,
        "gcp_project_id": PROJECT_ID,
        "gcp_instance_id": INSTANCE_ID,
        "reviewer_policy_sha256": "e" * 64,
        "g0_runtime_proof_sha256": G0_SHA,
        "g0_runtime_proof_generated_at": NOW.isoformat(),
        "g0_runtime_project_id": PROJECT_ID,
        "g0_runtime_zone": ZONE,
        "g0_runtime_vm_name": INSTANCE_NAME,
        "g0_runtime_instance_id": INSTANCE_ID,
        "operator_asserts_gateway_read_only": False,
        "requires_human_gateway_configuration_review": True,
        "signed_attestation_required": True,
        "broker_submission_allowed": False,
        "paper_order_submission_allowed": False,
        "live_execution_allowed": False,
        "automatic_promotion_allowed": False,
        "real_money_trading_allowed": False,
    }


def safe_handoff():
    return {
        "engine": "AURORA G7.10 Gateway Read-Only Reviewer Handoff Preflight",
        "status": "READY_FOR_INDEPENDENT_REVIEW",
        "ready_for_independent_review": True,
        "attestation_verified": False,
        "gateway_read_only_configuration_independently_attested": False,
        "failure_reasons": [],
        "handoff_request": handoff_request(),
        "broker_submission_allowed": False,
        "paper_order_submission_allowed": False,
        "live_execution_allowed": False,
        "automatic_promotion_allowed": False,
        "real_money_trading_allowed": False,
    }


def policy():
    return {
        "policy_version": 2,
        "reviewer_id": REVIEWER,
        "public_key_sha256": "f" * 64,
        "expected_instance_name": INSTANCE_NAME,
        "expected_zone": ZONE,
        "expected_project_id": PROJECT_ID,
        "expected_instance_id": INSTANCE_ID,
        "max_attestation_age_seconds": 7200,
        "allowed_clock_skew_seconds": 60,
    }


def runtime_identity():
    return {
        "status": "VERIFIED",
        "verified": True,
        "project_id": PROJECT_ID,
        "instance_name": INSTANCE_NAME,
        "zone": ZONE,
        "instance_id": INSTANCE_ID,
    }


class GatewayReviewPackageTests(unittest.TestCase):
    def test_pre_review_required_check_set_matches_current_g2_contract(self):
        self.assertEqual(
            _REQUIRED_G2_PASSED_CHECKS,
            EXPECTED_G2_REQUIRED_CHECKS - {
                "gateway_read_only_configuration_independently_attested"
            },
        )

    def test_safe_handoff_builds_unsigned_non_authorizing_package(self):
        result = build_unsigned_review_package(
            safe_handoff()
        )

        self.assertEqual(
            result["package_type"],
            PACKAGE_TYPE,
        )
        self.assertEqual(
            result["status"],
            "READY_FOR_INDEPENDENT_REVIEW_PACKAGE",
        )
        self.assertTrue(
            result["ready_for_independent_review"]
        )
        self.assertFalse(result["attestation_verified"])
        self.assertFalse(
            result[
                "gateway_read_only_configuration_independently_attested"
            ]
        )
        self.assertEqual(
            len(result["handoff_request_sha256"]),
            64,
        )

        template = result["unsigned_artifact_template"]
        self.assertEqual(template["schema_version"], 3)
        self.assertEqual(
            template["attestation_type"],
            ATTESTATION_TYPE,
        )
        self.assertEqual(
            template["decision"],
            "REVIEW_REQUIRED",
        )
        self.assertIsNone(template["attestation_id"])
        self.assertIsNone(template["captured_at_utc"])
        self.assertIsNone(template["expires_at_utc"])
        self.assertIsNone(template["read_only_api_enabled"])
        self.assertIsNone(template["evidence_sha256"])
        self.assertIsNone(template["signature_b64"])
        self.assertEqual(
            template["g0_runtime_proof_sha256"],
            G0_SHA,
        )
        self.assertEqual(
            template["signature_algorithm"],
            SIGNATURE_ALGORITHM,
        )
        for key in (
            "broker_submission_allowed",
            "paper_order_submission_allowed",
            "live_execution_allowed",
            "automatic_promotion_allowed",
            "real_money_trading_allowed",
        ):
            self.assertIs(result[key], False)

    def test_unsigned_template_cannot_be_reused_as_positive_attestation(self):
        template = build_unsigned_review_package(
            safe_handoff()
        )["unsigned_artifact_template"]

        result = evaluate_gateway_readonly_attestation(
            artifact=template,
            policy=policy(),
            current_git_sha=GIT_SHA,
            current_instance_name=INSTANCE_NAME,
            public_key_bytes=(
                b"-----BEGIN PUBLIC KEY-----\nTEST\n-----END PUBLIC KEY-----\n"
            ),
            signature_valid=True,
            runtime_cloud_identity=runtime_identity(),
            current_g0_proof_sha256=G0_SHA,
            now=NOW,
        )

        self.assertEqual(result["status"], "BLOCKED")
        for reason in (
            "attestation_id_uuid4",
            "decision_attested",
            "read_only_enabled",
            "evidence_sha256_valid",
            "captured_at_valid",
            "expires_at_valid",
            "signature_encoding_valid",
        ):
            self.assertIn(
                reason,
                result["failure_reasons"],
            )
        self.assertFalse(
            result[
                "gateway_read_only_configuration_independently_attested"
            ]
        )

    def test_unsafe_or_self_attesting_handoff_is_blocked(self):
        cases = []

        self_attesting = safe_handoff()
        self_attesting["attestation_verified"] = True
        cases.append(self_attesting)

        order_enabled = safe_handoff()
        order_enabled["paper_order_submission_allowed"] = True
        cases.append(order_enabled)

        bad_request = safe_handoff()
        bad_request["handoff_request"]["request_type"] = "WRONG"
        cases.append(bad_request)

        injected = safe_handoff()
        injected["handoff_request"]["raw_account_id"] = "DU1234567"
        cases.append(injected)

        for value in cases:
            with self.subTest(value=value):
                result = build_unsigned_review_package(value)
                self.assertEqual(result["status"], "BLOCKED")
                self.assertIsNone(
                    result["unsigned_artifact_template"]
                )
                self.assertNotIn(
                    "DU1234567",
                    json.dumps(result),
                )
                self.assertFalse(
                    result["paper_order_submission_allowed"]
                )

    def test_runtime_bound_package_rejects_wrong_probe_stage(self):
        diagnostic = g2_diagnostic()
        diagnostic["probe_stage"] = "POST_REVIEW_PROBE"
        result = build_runtime_bound_review_package(
            safe_handoff(),
            diagnostic,
            now=NOW,
        )
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(
            result["failure_reasons"],
            ["G2_DIAGNOSTIC_PROBE_STAGE_INVALID"],
        )

    def test_runtime_bound_package_requires_fresh_clean_g2_diagnostic(self):
        result = build_runtime_bound_review_package(
            safe_handoff(),
            g2_diagnostic(),
            now=NOW,
        )

        self.assertEqual(
            result["package_type"],
            RUNTIME_BOUND_PACKAGE_TYPE,
        )
        self.assertEqual(
            result["package_schema_version"],
            RUNTIME_BOUND_PACKAGE_SCHEMA_VERSION,
        )
        self.assertEqual(
            result["status"],
            "READY_FOR_INDEPENDENT_REVIEW_PACKAGE",
        )
        self.assertEqual(
            len(result["g2_diagnostic_proof_sha256"]),
            64,
        )
        summary = result["g2_diagnostic_summary"]
        self.assertEqual(
            summary["paper_account_fingerprints"],
            [ACCOUNT_FINGERPRINT],
        )
        self.assertEqual(summary["git_sha"], GIT_SHA)
        self.assertEqual(
            summary["gcp_instance_id"],
            INSTANCE_ID,
        )
        self.assertEqual(
            summary["g0_runtime_proof_sha256"],
            G0_SHA,
        )
        self.assertEqual(
            summary["only_required_failure"],
            "gateway_read_only_configuration_independently_attested",
        )
        self.assertIsNone(
            result["unsigned_artifact_template"]["evidence_sha256"]
        )
        self.assertNotIn(
            "DU1234567",
            json.dumps(result),
        )
        for key in (
            "broker_submission_allowed",
            "paper_order_submission_allowed",
            "live_execution_allowed",
            "automatic_promotion_allowed",
            "real_money_trading_allowed",
        ):
            self.assertIs(result[key], False)

    def test_runtime_bound_package_rejects_cross_vm_provenance(self):
        value = g2_diagnostic()
        value["runtime_provenance"]["runtime_cloud_identity"][
            "instance_id"
        ] = "9876543210987654321"

        result = build_runtime_bound_review_package(
            safe_handoff(),
            value,
            now=NOW,
        )

        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(
            result["failure_reasons"],
            ["G2_DIAGNOSTIC_GCE_IDENTITY_NOT_BOUND"],
        )

    def test_runtime_bound_package_rejects_different_g0_proof_digest(self):
        value = g2_diagnostic()
        value["runtime_provenance"][
            "g0_runtime_proof_sha256"
        ] = "b" * 64

        result = build_runtime_bound_review_package(
            safe_handoff(),
            value,
            now=NOW,
        )

        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(
            result["failure_reasons"],
            ["G2_DIAGNOSTIC_G0_PROOF_NOT_BOUND"],
        )

    def test_runtime_bound_package_rejects_missing_runtime_provenance(self):
        value = g2_diagnostic()
        value.pop("runtime_provenance")

        result = build_runtime_bound_review_package(
            safe_handoff(),
            value,
            now=NOW,
        )

        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(
            result["failure_reasons"],
            ["G2_DIAGNOSTIC_RUNTIME_PROVENANCE_INVALID"],
        )

    def test_runtime_bound_package_rejects_stale_or_wrong_commit_g2(self):
        stale = g2_diagnostic(
            (NOW - timedelta(seconds=301)).isoformat()
        )
        stale_result = build_runtime_bound_review_package(
            safe_handoff(),
            stale,
            now=NOW,
        )
        self.assertEqual(stale_result["status"], "BLOCKED")
        self.assertEqual(
            stale_result["failure_reasons"],
            ["G2_DIAGNOSTIC_NOT_FRESH"],
        )

        wrong_commit = g2_diagnostic()
        wrong_commit["git_sha"] = "b" * 40
        wrong_result = build_runtime_bound_review_package(
            safe_handoff(),
            wrong_commit,
            now=NOW,
        )
        self.assertEqual(wrong_result["status"], "BLOCKED")
        self.assertEqual(
            wrong_result["failure_reasons"],
            ["G2_DIAGNOSTIC_GIT_SHA_NOT_BOUND"],
        )

    def test_runtime_bound_package_rejects_mutation_or_client_binding_regression(self):
        cases = []

        mutation_enabled = g2_diagnostic()
        mutation_enabled["snapshot"][
            "broker_mutation_surface_hard_blocked"
        ] = False
        cases.append(mutation_enabled)

        binding_observation = g2_diagnostic()
        binding_observation["snapshot"][
            "open_order_observation_mode"
        ] = "REQ_OPEN_ORDERS_BINDING"
        cases.append(binding_observation)

        client_zero = g2_diagnostic()
        client_zero["snapshot"]["config"]["client_id"] = 0
        client_zero["snapshot"]["config"]["client_id_valid"] = False
        client_zero["snapshot"][
            "client_zero_binding_hard_blocked"
        ] = False
        cases.append(client_zero)

        for value in cases:
            with self.subTest(value=value):
                result = build_runtime_bound_review_package(
                    safe_handoff(),
                    value,
                    now=NOW,
                )
                self.assertEqual(result["status"], "BLOCKED")
                self.assertEqual(
                    result["failure_reasons"],
                    ["G2_DIAGNOSTIC_CONNECTOR_SAFETY_INVALID"],
                )

    def test_runtime_bound_package_rejects_raw_or_unverified_account_identity(self):
        value = g2_diagnostic()
        value["snapshot"]["accounts"] = ["DU1234567"]
        value["snapshot"]["paper_account_guard"][
            "verified_account_fingerprints"
        ] = ["DU1234567"]

        result = build_runtime_bound_review_package(
            safe_handoff(),
            value,
            now=NOW,
        )

        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(
            result["failure_reasons"],
            ["G2_DIAGNOSTIC_ACCOUNT_IDENTITY_INVALID"],
        )
        self.assertNotIn("DU1234567", json.dumps(result))

    def test_runtime_bound_package_accepts_only_attestation_as_required_failure(self):
        value = g2_diagnostic()
        for item in value["readiness"]["checks"]:
            if item["check"] == "gateway_connected":
                item["passed"] = False
                break
        value["readiness"]["required_failure_count"] = 2

        result = build_runtime_bound_review_package(
            safe_handoff(),
            value,
            now=NOW,
        )

        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(
            result["failure_reasons"],
            ["G2_DIAGNOSTIC_REQUIRED_CHECKS_NOT_CLEAN"],
        )

    def test_runtime_bound_package_rejects_pre_review_verified_attestation(self):
        value = g2_diagnostic()
        value["gateway_read_only_attestation"].update({
            "status": "VERIFIED",
            "verified": True,
            "gateway_read_only_configuration_independently_attested": True,
        })

        result = build_runtime_bound_review_package(
            safe_handoff(),
            value,
            now=NOW,
        )

        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(
            result["failure_reasons"],
            ["G2_DIAGNOSTIC_PRE_REVIEW_ATTESTATION_STATE_INVALID"],
        )

    def test_installed_g2_loader_accepts_owner_only_regular_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "latest.json"
            payload = {"safe": True}
            path.write_text(
                json.dumps(payload),
                encoding="utf-8",
            )
            path.chmod(0o600)

            with patch.object(
                review_package,
                "DEFAULT_G2_DIAGNOSTIC_PROOF",
                path,
            ):
                loaded = (
                    review_package.load_installed_g2_diagnostic_proof()
                )

        self.assertEqual(loaded, payload)

    def test_installed_g2_loader_rejects_group_or_world_access(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "latest.json"
            path.write_text(
                json.dumps({"safe": True}),
                encoding="utf-8",
            )
            path.chmod(0o644)

            with patch.object(
                review_package,
                "DEFAULT_G2_DIAGNOSTIC_PROOF",
                path,
            ):
                loaded = (
                    review_package.load_installed_g2_diagnostic_proof()
                )

        self.assertEqual(loaded, {})

    def test_installed_g2_loader_rejects_symlink_and_hardlink(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "target.json"
            target.write_text(
                json.dumps({"safe": True}),
                encoding="utf-8",
            )
            target.chmod(0o600)

            symlink = root / "symlink.json"
            symlink.symlink_to(target)

            with patch.object(
                review_package,
                "DEFAULT_G2_DIAGNOSTIC_PROOF",
                symlink,
            ):
                self.assertEqual(
                    review_package.load_installed_g2_diagnostic_proof(),
                    {},
                )

            hardlink = root / "hardlink.json"
            hardlink.hardlink_to(target)

            with patch.object(
                review_package,
                "DEFAULT_G2_DIAGNOSTIC_PROOF",
                hardlink,
            ):
                self.assertEqual(
                    review_package.load_installed_g2_diagnostic_proof(),
                    {},
                )

    def test_installed_g2_loader_rejects_duplicate_json_keys(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "latest.json"
            path.write_text(
                '{"safe":true,"safe":false}',
                encoding="utf-8",
            )
            path.chmod(0o600)

            with patch.object(
                review_package,
                "DEFAULT_G2_DIAGNOSTIC_PROOF",
                path,
            ):
                loaded = (
                    review_package.load_installed_g2_diagnostic_proof()
                )

        self.assertEqual(loaded, {})

    def test_source_has_no_signing_private_key_or_file_mutation_path(self):
        import scripts.gateway_review_package as module

        source = inspect.getsource(module).lower()
        for token in (
            "private key",
            "pkeyutl",
            "signature_valid=true",
            "write_text",
            "write_bytes",
            "chmod",
            "os.replace",
            "decision\": \"attested",
        ):
            self.assertNotIn(token, source)


if __name__ == "__main__":
    unittest.main()
