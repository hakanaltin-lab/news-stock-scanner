"""G7.11 tests for the non-attesting reviewer package builder."""

from datetime import datetime, timezone
import inspect
import json
import unittest

from scripts.gateway_review_package import (
    PACKAGE_TYPE,
    build_unsigned_review_package,
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

        for value in cases:
            with self.subTest(value=value):
                result = build_unsigned_review_package(value)
                self.assertEqual(result["status"], "BLOCKED")
                self.assertIsNone(
                    result["unsigned_artifact_template"]
                )
                self.assertFalse(
                    result["paper_order_submission_allowed"]
                )

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
