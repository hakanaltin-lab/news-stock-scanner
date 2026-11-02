"""G7.6 tests for the non-attesting operator/reviewer handoff preflight."""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from engines.gateway_attestation_handoff import (
    EXPECTED_INSTANCE_NAME,
    EXPECTED_ZONE,
    HANDOFF_REQUEST_TYPE,
    evaluate_reviewer_handoff_preflight,
)
from engines.gateway_readonly_attestation_verifier import (
    ATTESTATION_TYPE,
    evaluate_gateway_readonly_attestation,
)


NOW = datetime(2026, 11, 2, 8, 0, tzinfo=timezone.utc)
PUBLIC_KEY = (
    b"-----BEGIN PUBLIC KEY-----\n"
    b"TEST-ONLY-PUBLIC-MATERIAL\n"
    b"-----END PUBLIC KEY-----\n"
)
GIT_SHA = "a" * 40


def g0_proof():
    return {
        "engine": "AURORA V8.9.20 G0-G1 Runtime Proof",
        "generated_at": NOW.isoformat(),
        "project_id": "project-ce9773ef-6814-469c-92b",
        "zone": EXPECTED_ZONE,
        "vm_name": EXPECTED_INSTANCE_NAME,
        "status": "G0_G1_VERIFIED",
        "checks": {
            "budget_guard_passed": True,
            "vm_identity": True,
            "vm_running": True,
            "vm_hardened": True,
            "network_contract": True,
            "iap_ssh_only_rule": True,
            "public_private_ports_denied": True,
            "no_public_allow_for_sensitive_ports": True,
        },
        "failure_reasons": [],
        "external_ip_present": True,
        "public_sensitive_allow_rules": [],
        "broker_submission_allowed": False,
        "paper_order_submission_allowed": False,
        "live_execution_allowed": False,
        "automatic_promotion_allowed": False,
    }


def policy():
    return {
        "policy_version": 1,
        "reviewer_id": "aurora-independent-reviewer",
        "public_key_sha256": hashlib.sha256(PUBLIC_KEY).hexdigest(),
        "expected_instance_name": EXPECTED_INSTANCE_NAME,
        "expected_zone": EXPECTED_ZONE,
        "max_attestation_age_seconds": 28800,
        "allowed_clock_skew_seconds": 60,
    }


class GatewayAttestationHandoffTests(unittest.TestCase):
    def evaluate(self, **overrides):
        arguments = {
            "policy": policy(),
            "public_key_bytes": PUBLIC_KEY,
            "current_git_sha": GIT_SHA,
            "current_instance_name": EXPECTED_INSTANCE_NAME,
            "repository_clean": True,
            "openssl_available": True,
            "g0_proof": g0_proof(),
            "now": NOW,
        }
        arguments.update(overrides)
        return evaluate_reviewer_handoff_preflight(
            **arguments
        )

    def test_valid_setup_is_ready_for_review_but_never_attested(self):
        result = self.evaluate()

        self.assertEqual(
            result["status"],
            "READY_FOR_INDEPENDENT_REVIEW",
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
        self.assertFalse(
            result["paper_order_submission_allowed"]
        )
        self.assertFalse(
            result["live_execution_allowed"]
        )
        self.assertFalse(
            result["real_money_trading_allowed"]
        )

        request = result["handoff_request"]
        self.assertEqual(
            request["request_type"],
            HANDOFF_REQUEST_TYPE,
        )
        self.assertEqual(
            request["requested_control"],
            ATTESTATION_TYPE,
        )
        self.assertFalse(
            request["operator_asserts_gateway_read_only"]
        )
        self.assertTrue(
            request[
                "requires_human_gateway_configuration_review"
            ]
        )
        self.assertTrue(
            request["signed_attestation_required"]
        )
        self.assertEqual(
            request["g0_runtime_zone"],
            EXPECTED_ZONE,
        )
        self.assertEqual(
            request["g0_runtime_vm_name"],
            EXPECTED_INSTANCE_NAME,
        )
        self.assertEqual(
            len(request["reviewer_policy_sha256"]),
            64,
        )
        self.assertEqual(
            len(request["g0_runtime_proof_sha256"]),
            64,
        )

    def test_handoff_request_cannot_be_reused_as_attestation(self):
        request = self.evaluate()["handoff_request"]

        verifier_result = (
            evaluate_gateway_readonly_attestation(
                artifact=request,
                policy=policy(),
                current_git_sha=GIT_SHA,
                current_instance_name=EXPECTED_INSTANCE_NAME,
                public_key_bytes=PUBLIC_KEY,
                signature_valid=True,
                repository_clean=True,
                now=NOW,
            )
        )

        self.assertEqual(
            verifier_result["status"],
            "BLOCKED",
        )
        self.assertIn(
            "artifact_field_set_exact",
            verifier_result["failure_reasons"],
        )
        self.assertFalse(
            verifier_result[
                "gateway_read_only_configuration_independently_attested"
            ]
        )

    def test_dirty_repo_wrong_instance_or_missing_openssl_blocks(self):
        cases = [
            (
                {"repository_clean": False},
                "repository_clean",
            ),
            (
                {
                    "current_instance_name":
                    "not-the-approved-vps"
                },
                "runtime_instance_matches_policy",
            ),
            (
                {"openssl_available": False},
                "openssl_available",
            ),
        ]

        for overrides, expected_failure in cases:
            with self.subTest(
                expected_failure=expected_failure
            ):
                result = self.evaluate(
                    **overrides
                )
                self.assertEqual(
                    result["status"],
                    "BLOCKED",
                )
                self.assertIsNone(
                    result["handoff_request"]
                )
                self.assertIn(
                    expected_failure,
                    result["failure_reasons"],
                )

    def test_g0_runtime_proof_is_required_and_bound(self):
        missing = self.evaluate(
            g0_proof={}
        )
        self.assertEqual(
            missing["status"],
            "BLOCKED",
        )
        self.assertIn(
            "g0_runtime_verified",
            missing["failure_reasons"],
        )

        malformed = g0_proof()
        malformed["failure_reasons"] = "none"
        malformed_result = self.evaluate(
            g0_proof=malformed
        )
        self.assertIn(
            "g0_runtime_verified",
            malformed_result["failure_reasons"],
        )

        exposed = g0_proof()
        exposed["public_sensitive_allow_rules"] = [
            {"name": "bad-rule", "ports": [4002]}
        ]
        exposed_result = self.evaluate(
            g0_proof=exposed
        )
        self.assertIn(
            "g0_runtime_verified",
            exposed_result["failure_reasons"],
        )

        wrong_zone = g0_proof()
        wrong_zone["zone"] = "us-central1-a"
        zone_result = self.evaluate(
            g0_proof=wrong_zone
        )
        self.assertIn(
            "g0_runtime_identity_bound",
            zone_result["failure_reasons"],
        )

        weakened = g0_proof()
        weakened["checks"][
            "public_private_ports_denied"
        ] = False
        weakened_result = self.evaluate(
            g0_proof=weakened
        )
        self.assertIn(
            "g0_runtime_checks_complete",
            weakened_result["failure_reasons"],
        )

        stale = g0_proof()
        stale["generated_at"] = "2026-10-31T07:59:00+00:00"
        stale_result = self.evaluate(
            g0_proof=stale
        )
        self.assertIn(
            "g0_runtime_proof_fresh",
            stale_result["failure_reasons"],
        )

        unsafe = g0_proof()
        unsafe["paper_order_submission_allowed"] = True
        unsafe_result = self.evaluate(
            g0_proof=unsafe
        )
        self.assertIn(
            "g0_order_permissions_blocked",
            unsafe_result["failure_reasons"],
        )

    def test_unapproved_zone_or_instance_policy_blocks(self):
        for key, value, expected_failure in (
            (
                "expected_zone",
                "us-central1-a",
                "approved_zone_policy",
            ),
            (
                "expected_instance_name",
                "different-vps",
                "approved_instance_policy",
            ),
        ):
            with self.subTest(key=key):
                modified = policy()
                modified[key] = value
                result = self.evaluate(
                    policy=modified
                )
                self.assertEqual(
                    result["status"],
                    "BLOCKED",
                )
                self.assertIn(
                    expected_failure,
                    result["failure_reasons"],
                )

    def test_public_key_pin_or_material_mismatch_blocks(self):
        modified = policy()
        modified["public_key_sha256"] = "b" * 64
        mismatch = self.evaluate(
            policy=modified
        )
        self.assertIn(
            "public_key_matches_policy",
            mismatch["failure_reasons"],
        )

        private_key = (
            b"-----BEGIN PRIVATE KEY-----\n"
            b"DO-NOT-STORE-HERE\n"
            b"-----END PRIVATE KEY-----\n"
        )
        private = self.evaluate(
            public_key_bytes=private_key
        )
        self.assertIn(
            "reviewer_public_key_material_valid",
            private["failure_reasons"],
        )

    def test_policy_is_strict_and_boolean_versions_do_not_pass(self):
        modified = policy()
        modified["policy_version"] = True
        result = self.evaluate(
            policy=modified
        )
        self.assertIn(
            "policy_version",
            result["failure_reasons"],
        )

        modified = policy()
        modified["unexpected"] = True
        extra = self.evaluate(
            policy=modified
        )
        self.assertIn(
            "policy_field_set_exact",
            extra["failure_reasons"],
        )

    def test_handoff_contains_no_account_balance_or_order_authorization(self):
        encoded = json.dumps(
            self.evaluate(),
            sort_keys=True,
        ).lower()

        for forbidden in (
            "account_id",
            "account_number",
            "netliquidation",
            "totalcashvalue",
            "availablefunds",
            "password",
            "private key",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(
                    forbidden,
                    encoded,
                )

        self.assertNotIn(
            '"paper_order_submission_allowed": true',
            encoded,
        )
        self.assertNotIn(
            '"live_execution_allowed": true',
            encoded,
        )
        self.assertNotIn(
            '"real_money_trading_allowed": true',
            encoded,
        )

    def test_cli_without_installed_root_trust_fails_closed(self):
        root = Path(__file__).resolve().parents[1]
        completed = subprocess.run(
            [
                sys.executable,
                str(
                    root
                    / "scripts"
                    / "gateway_readonly_attestation_handoff.py"
                ),
            ],
            capture_output=True,
            text=True,
            check=False,
        )

        # CI/dev hosts intentionally lack the production /etc/aurora trust root.
        if completed.returncode == 0:
            payload = json.loads(completed.stdout)
            self.assertEqual(
                payload["status"],
                "READY_FOR_INDEPENDENT_REVIEW",
            )
            self.assertFalse(
                payload["attestation_verified"]
            )
        else:
            self.assertEqual(
                completed.returncode,
                2,
            )
            payload = json.loads(completed.stdout)
            self.assertEqual(
                payload["status"],
                "BLOCKED",
            )
            self.assertFalse(
                payload[
                    "gateway_read_only_configuration_independently_attested"
                ]
            )


if __name__ == "__main__":
    unittest.main()
