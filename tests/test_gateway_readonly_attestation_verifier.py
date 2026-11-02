"""G7.5 tests for independently signed Gateway Read-Only attestations."""

import base64
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from uuid import UUID

from engines.gateway_readonly_attestation_verifier import (
    ATTESTATION_TYPE,
    SIGNATURE_ALGORITHM,
    _canonical_signed_payload,
    _load_json_bytes,
    _trusted_root_file,
    _verify_ed25519_signature,
    DuplicateJsonKeyError,
    evaluate_gateway_readonly_attestation,
)


NOW = datetime(2026, 11, 2, 7, 0, tzinfo=timezone.utc)
GIT_SHA = "a" * 40
INSTANCE = "aurora-trading-vps"
ZONE = "europe-west3-a"
PROJECT_ID = "project-ce9773ef-6814-469c-92b"
INSTANCE_ID = "1234567890123456789"
REVIEWER = "aurora-independent-reviewer"
G0_PROOF_SHA256 = "c" * 64


def artifact():
    return {
        "schema_version": 3,
        "attestation_id": "11111111-1111-4111-8111-111111111111",
        "attestation_type": ATTESTATION_TYPE,
        "decision": "ATTESTED",
        "reviewer_id": REVIEWER,
        "captured_at_utc": (NOW - timedelta(minutes=5)).isoformat(),
        "expires_at_utc": (NOW + timedelta(hours=1)).isoformat(),
        "git_sha": GIT_SHA,
        "instance_name": INSTANCE,
        "zone": ZONE,
        "gcp_project_id": PROJECT_ID,
        "gcp_instance_id": INSTANCE_ID,
        "broker_mode": "PAPER",
        "gateway_port": 4002,
        "read_only_api_enabled": True,
        "evidence_sha256": "b" * 64,
        "g0_runtime_proof_sha256": G0_PROOF_SHA256,
        "signature_algorithm": SIGNATURE_ALGORITHM,
        "signature_b64": base64.b64encode(b"x" * 64).decode("ascii"),
    }


def policy(public_key_bytes):
    return {
        "policy_version": 2,
        "reviewer_id": REVIEWER,
        "public_key_sha256": hashlib.sha256(public_key_bytes).hexdigest(),
        "expected_instance_name": INSTANCE,
        "expected_zone": ZONE,
        "expected_project_id": PROJECT_ID,
        "expected_instance_id": INSTANCE_ID,
        "max_attestation_age_seconds": 7200,
        "allowed_clock_skew_seconds": 60,
    }


def runtime_identity():
    return {
        "engine": "AURORA G7.7 GCE Runtime Identity",
        "status": "VERIFIED",
        "verified": True,
        "project_id": PROJECT_ID,
        "instance_name": INSTANCE,
        "zone": ZONE,
        "instance_id": INSTANCE_ID,
        "failure_reasons": [],
    }


class GatewayReadOnlyAttestationTests(unittest.TestCase):
    def evaluate(
        self,
        data=None,
        policy_data=None,
        public_key=b"-----BEGIN PUBLIC KEY-----\nTEST\n-----END PUBLIC KEY-----\n",
        signature_valid=True,
    ):
        data = artifact() if data is None else data
        policy_data = policy(public_key) if policy_data is None else policy_data
        return evaluate_gateway_readonly_attestation(
            artifact=data,
            policy=policy_data,
            current_git_sha=GIT_SHA,
            current_instance_name=INSTANCE,
            public_key_bytes=public_key,
            signature_valid=signature_valid,
            runtime_cloud_identity=runtime_identity(),
            current_g0_proof_sha256=G0_PROOF_SHA256,
            now=NOW,
        )

    def test_valid_independent_attestation_verifies(self):
        result = self.evaluate()
        self.assertEqual(result["status"], "VERIFIED")
        self.assertTrue(result["verified"])
        self.assertTrue(
            result[
                "gateway_read_only_configuration_independently_attested"
            ]
        )
        self.assertEqual(result["failure_reasons"], [])
        self.assertEqual(result["git_sha"], GIT_SHA)
        self.assertEqual(
            result["g0_runtime_proof_sha256"],
            G0_PROOF_SHA256,
        )

    def test_g0_runtime_proof_digest_is_signed_and_runtime_bound(self):
        missing = artifact()
        missing.pop("g0_runtime_proof_sha256")
        first = self.evaluate(data=missing)
        self.assertEqual(first["status"], "BLOCKED")
        self.assertIn(
            "artifact_field_set_exact",
            first["failure_reasons"],
        )

        malformed = artifact()
        malformed["g0_runtime_proof_sha256"] = "not-a-digest"
        second = self.evaluate(data=malformed)
        self.assertIn(
            "g0_runtime_proof_sha256_valid",
            second["failure_reasons"],
        )

        mismatch = evaluate_gateway_readonly_attestation(
            artifact=artifact(),
            policy=policy(
                b"-----BEGIN PUBLIC KEY-----\nTEST\n-----END PUBLIC KEY-----\n"
            ),
            current_git_sha=GIT_SHA,
            current_instance_name=INSTANCE,
            public_key_bytes=(
                b"-----BEGIN PUBLIC KEY-----\nTEST\n-----END PUBLIC KEY-----\n"
            ),
            signature_valid=True,
            runtime_cloud_identity=runtime_identity(),
            current_g0_proof_sha256="d" * 64,
            now=NOW,
        )
        self.assertEqual(mismatch["status"], "BLOCKED")
        self.assertIn(
            "g0_runtime_proof_bound",
            mismatch["failure_reasons"],
        )

    def test_signature_failure_blocks(self):
        result = self.evaluate(signature_valid=False)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("ed25519_signature_valid", result["failure_reasons"])
        self.assertFalse(
            result[
                "gateway_read_only_configuration_independently_attested"
            ]
        )

    def test_wrong_git_sha_or_instance_blocks(self):
        wrong_sha = self.evaluate(
            data={**artifact(), "git_sha": "c" * 40}
        )
        self.assertIn("git_sha_bound", wrong_sha["failure_reasons"])

        result = evaluate_gateway_readonly_attestation(
            artifact=artifact(),
            policy=policy(
                b"-----BEGIN PUBLIC KEY-----\nTEST\n-----END PUBLIC KEY-----\n"
            ),
            current_git_sha=GIT_SHA,
            current_instance_name="different-vps",
            public_key_bytes=(
                b"-----BEGIN PUBLIC KEY-----\nTEST\n-----END PUBLIC KEY-----\n"
            ),
            signature_valid=True,
            runtime_cloud_identity=runtime_identity(),
            current_g0_proof_sha256=G0_PROOF_SHA256,
            now=NOW,
        )
        self.assertIn("runtime_instance_bound", result["failure_reasons"])

    def test_dirty_repository_blocks_even_with_valid_signature(self):
        result = evaluate_gateway_readonly_attestation(
            artifact=artifact(),
            policy=policy(b"-----BEGIN PUBLIC KEY-----\nTEST\n-----END PUBLIC KEY-----\n"),
            current_git_sha=GIT_SHA,
            current_instance_name=INSTANCE,
            public_key_bytes=b"-----BEGIN PUBLIC KEY-----\nTEST\n-----END PUBLIC KEY-----\n",
            signature_valid=True,
            repository_clean=False,
            runtime_cloud_identity=runtime_identity(),
            current_g0_proof_sha256=G0_PROOF_SHA256,
            now=NOW,
        )
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("repository_clean", result["failure_reasons"])

    def test_gce_runtime_identity_must_match_signed_artifact_and_policy(self):
        wrong_instance = runtime_identity()
        wrong_instance["instance_id"] = "9876543210987654321"
        result = evaluate_gateway_readonly_attestation(
            artifact=artifact(),
            policy=policy(
                b"-----BEGIN PUBLIC KEY-----\nTEST\n-----END PUBLIC KEY-----\n"
            ),
            current_git_sha=GIT_SHA,
            current_instance_name=INSTANCE,
            public_key_bytes=(
                b"-----BEGIN PUBLIC KEY-----\nTEST\n-----END PUBLIC KEY-----\n"
            ),
            signature_valid=True,
            runtime_cloud_identity=wrong_instance,
            current_g0_proof_sha256=G0_PROOF_SHA256,
            now=NOW,
        )
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn(
            "gce_instance_id_runtime_bound",
            result["failure_reasons"],
        )

        wrong_project = artifact()
        wrong_project["gcp_project_id"] = "different-project"
        second = self.evaluate(data=wrong_project)
        self.assertIn(
            "gcp_project_id_format",
            second["failure_reasons"],
        )

        wrong_policy = policy(
            b"-----BEGIN PUBLIC KEY-----\nTEST\n-----END PUBLIC KEY-----\n"
        )
        wrong_policy["expected_instance_id"] = "9876543210987654321"
        third = self.evaluate(
            policy_data=wrong_policy
        )
        self.assertIn(
            "gcp_instance_matches_policy",
            third["failure_reasons"],
        )

    def test_gcp_identity_fields_require_string_types(self):
        numeric_artifact = artifact()
        numeric_artifact["gcp_instance_id"] = 1234567890123456789
        first = self.evaluate(
            data=numeric_artifact
        )
        self.assertIn(
            "gcp_instance_id_format",
            first["failure_reasons"],
        )

        numeric_policy = policy(
            b"-----BEGIN PUBLIC KEY-----\nTEST\n-----END PUBLIC KEY-----\n"
        )
        numeric_policy["expected_instance_id"] = 1234567890123456789
        second = self.evaluate(
            policy_data=numeric_policy
        )
        self.assertIn(
            "policy_instance_id_format",
            second["failure_reasons"],
        )

        numeric_project = artifact()
        numeric_project["gcp_project_id"] = 123
        third = self.evaluate(
            data=numeric_project
        )
        self.assertIn(
            "gcp_project_id_format",
            third["failure_reasons"],
        )

    def test_missing_or_blocked_gce_runtime_identity_blocks(self):
        for runtime_identity_value in (
            {},
            {
                "status": "BLOCKED",
                "verified": False,
                "failure_reasons": ["metadata unavailable"],
            },
        ):
            with self.subTest(runtime_identity=runtime_identity_value):
                result = evaluate_gateway_readonly_attestation(
                    artifact=artifact(),
                    policy=policy(
                        b"-----BEGIN PUBLIC KEY-----\nTEST\n-----END PUBLIC KEY-----\n"
                    ),
                    current_git_sha=GIT_SHA,
                    current_instance_name=INSTANCE,
                    public_key_bytes=(
                        b"-----BEGIN PUBLIC KEY-----\nTEST\n-----END PUBLIC KEY-----\n"
                    ),
                    signature_valid=True,
                    runtime_cloud_identity=runtime_identity_value,
                    current_g0_proof_sha256=G0_PROOF_SHA256,
                    now=NOW,
                )
                self.assertEqual(result["status"], "BLOCKED")
                self.assertIn(
                    "gce_runtime_identity_verified",
                    result["failure_reasons"],
                )

    def test_expired_future_or_overlong_attestation_blocks(self):
        expired = artifact()
        expired["captured_at_utc"] = (NOW - timedelta(hours=3)).isoformat()
        expired["expires_at_utc"] = (NOW - timedelta(hours=2)).isoformat()
        first = self.evaluate(data=expired)
        self.assertIn("attestation_not_expired", first["failure_reasons"])
        self.assertIn(
            "attestation_age_within_policy",
            first["failure_reasons"],
        )

        future = artifact()
        future["captured_at_utc"] = (NOW + timedelta(minutes=10)).isoformat()
        future["expires_at_utc"] = (NOW + timedelta(minutes=20)).isoformat()
        second = self.evaluate(data=future)
        self.assertIn("capture_not_in_future", second["failure_reasons"])

        overlong = artifact()
        overlong["expires_at_utc"] = (NOW + timedelta(hours=4)).isoformat()
        third = self.evaluate(data=overlong)
        self.assertIn(
            "attestation_validity_window_within_policy",
            third["failure_reasons"],
        )

    def test_boolean_schema_versions_and_non_utc_timestamps_block(self):
        bool_schema = artifact()
        bool_schema["schema_version"] = True
        first = self.evaluate(data=bool_schema)
        self.assertIn(
            "artifact_schema_version",
            first["failure_reasons"],
        )

        public_key = (
            b"-----BEGIN PUBLIC KEY-----\nTEST\n-----END PUBLIC KEY-----\n"
        )
        bad_policy = policy(public_key)
        bad_policy["policy_version"] = True
        second = self.evaluate(policy_data=bad_policy)
        self.assertIn(
            "policy_version",
            second["failure_reasons"],
        )

        non_utc = artifact()
        non_utc["captured_at_utc"] = "2026-11-02T10:00:00+03:00"
        third = self.evaluate(data=non_utc)
        self.assertIn(
            "captured_at_valid",
            third["failure_reasons"],
        )

    def test_unknown_or_missing_fields_block(self):
        extra = artifact()
        extra["operator_self_attested"] = True
        self.assertIn(
            "artifact_field_set_exact",
            self.evaluate(data=extra)["failure_reasons"],
        )

        missing = artifact()
        missing.pop("evidence_sha256")
        self.assertIn(
            "artifact_field_set_exact",
            self.evaluate(data=missing)["failure_reasons"],
        )

    def test_policy_key_pin_and_reviewer_must_match(self):
        bad_policy = policy(b"-----BEGIN PUBLIC KEY-----\nTEST\n-----END PUBLIC KEY-----\n")
        bad_policy["public_key_sha256"] = "d" * 64
        result = self.evaluate(policy_data=bad_policy)
        self.assertIn(
            "public_key_matches_policy",
            result["failure_reasons"],
        )

        bad_reviewer = artifact()
        bad_reviewer["reviewer_id"] = "different-reviewer"
        second = self.evaluate(data=bad_reviewer)
        self.assertIn(
            "reviewer_matches_policy",
            second["failure_reasons"],
        )

    def test_private_key_material_is_never_accepted_as_reviewer_key(self):
        private_material = (
            b"-----BEGIN PRIVATE KEY-----\nTEST\n-----END PRIVATE KEY-----\n"
        )
        result = self.evaluate(
            public_key=private_material,
            policy_data=policy(private_material),
        )
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn(
            "reviewer_public_key_material_valid",
            result["failure_reasons"],
        )

    def test_duplicate_json_keys_are_rejected_before_verification(self):
        raw = (
            b'{"schema_version":1,"schema_version":1}'
        )
        with self.assertRaises(DuplicateJsonKeyError):
            _load_json_bytes(raw)

    def test_root_trust_boundary_rejects_normal_user_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "policy.json"
            path.write_text("{}", encoding="utf-8")
            trusted, reason = _trusted_root_file(path, max_bytes=8192)

        if hasattr(Path("/").stat(), "st_uid") and path is not None:
            # CI/local tests normally run non-root. When a test runner itself is
            # root, ownership may satisfy the root check; permissions remain safe.
            if trusted:
                self.assertIsNone(reason)
            else:
                self.assertIn(
                    reason,
                    {
                        "TRUSTED_PARENT_NOT_ROOT_OWNED",
                        "TRUSTED_PARENT_GROUP_OR_WORLD_WRITABLE",
                        "TRUSTED_FILE_NOT_ROOT_OWNED",
                    },
                )

    @unittest.skipUnless(
        Path("/usr/bin/openssl").is_file(),
        "OpenSSL is required for Ed25519 verifier integration",
    )
    def test_real_ed25519_signature_verification_and_tamper_detection(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            private_key = directory / "reviewer-private.pem"
            public_key = directory / "reviewer-public.pem"
            payload_file = directory / "payload.json"
            signature_file = directory / "signature.bin"

            subprocess.run(
                [
                    "/usr/bin/openssl",
                    "genpkey",
                    "-algorithm",
                    "ED25519",
                    "-out",
                    str(private_key),
                ],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            subprocess.run(
                [
                    "/usr/bin/openssl",
                    "pkey",
                    "-in",
                    str(private_key),
                    "-pubout",
                    "-out",
                    str(public_key),
                ],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

            data = artifact()
            payload = _canonical_signed_payload(data)
            payload_file.write_bytes(payload)

            subprocess.run(
                [
                    "/usr/bin/openssl",
                    "pkeyutl",
                    "-sign",
                    "-inkey",
                    str(private_key),
                    "-rawin",
                    "-in",
                    str(payload_file),
                    "-out",
                    str(signature_file),
                ],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

            public_bytes = public_key.read_bytes()
            signature = signature_file.read_bytes()

            self.assertEqual(len(signature), 64)
            self.assertTrue(
                _verify_ed25519_signature(
                    public_bytes,
                    payload,
                    signature,
                )
            )

            data["read_only_api_enabled"] = False
            tampered_payload = _canonical_signed_payload(data)
            self.assertFalse(
                _verify_ed25519_signature(
                    public_bytes,
                    tampered_payload,
                    signature,
                )
            )

    def test_uuid_must_be_canonical_v4(self):
        data = artifact()
        data["attestation_id"] = str(UUID(int=0))
        result = self.evaluate(data=data)
        self.assertIn(
            "attestation_id_uuid4",
            result["failure_reasons"],
        )


if __name__ == "__main__":
    unittest.main()
