"""G8.15 tests for independently signed adapter source attestation."""

from datetime import datetime, timedelta, timezone
import base64
import hashlib
import inspect
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from engines.paper_adapter_source_attestation import (
    ATTESTATION_TYPE,
    SIGNATURE_ALGORITHM,
    canonical_signed_payload,
    evaluate_source_attestation,
)
from engines.paper_adapter_source_handoff import (
    evaluate_source_review_handoff,
)
from engines.paper_adapter_source_review import (
    EXPECTED_G8_12_CHECKS,
    evaluate_adapter_source_review,
)
from engines.paper_connector_review_prerequisite import (
    ENGINE_VERSION as PREREQUISITE_ENGINE_VERSION,
)
from scripts import verify_adapter_source_attestation as cli


NOW = datetime(2026, 11, 2, 15, 30, tzinfo=timezone.utc)
GIT_SHA = "a" * 40
AUTHORIZATION_ID = "11111111-1111-4111-8111-111111111111"
EVIDENCE_RUN_ID = "22222222-2222-4222-8222-222222222222"
INSTANCE_ID = "1234567890123456789"
ACCOUNT = "IBKR-A1B2C3D4E5"
REVIEWER = "aurora-adapter-source-reviewer"
REVIEW_ID = "33333333-3333-4333-8333-333333333333"
PUBLIC_KEY = (
    b"-----BEGIN PUBLIC KEY-----\n"
    b"TEST-SOURCE-REVIEW-KEY\n"
    b"-----END PUBLIC KEY-----\n"
)
REPO_ROOT = Path(__file__).resolve().parents[1]
SKELETON_PATH = (
    REPO_ROOT
    / "broker_engine/ibkr_paper_adapter_review_skeleton.py"
)


def runtime_permissions():
    return {
        "implementation_allowed": False,
        "connection_allowed": False,
        "broker_request_materialization_allowed": False,
        "broker_order_object_allowed": False,
        "automatic_retry_allowed": False,
        "automatic_cancel_allowed": False,
        "automatic_modify_allowed": False,
        "broker_submission_allowed": False,
        "paper_order_submission_allowed": False,
        "live_execution_allowed": False,
        "automatic_promotion_allowed": False,
        "real_money_trading_allowed": False,
    }


def prerequisite():
    return {
        "engine": PREREQUISITE_ENGINE_VERSION,
        "generated_at": (
            NOW - timedelta(seconds=5)
        ).isoformat(),
        "status": "READY_FOR_PAPER_CONNECTOR_SOURCE_REVIEW",
        "checks": {
            name: True
            for name in EXPECTED_G8_12_CHECKS
        },
        "g5_validation_sha256": "1" * 64,
        "authorization_id": AUTHORIZATION_ID,
        "authorization_artifact_sha256": "2" * 64,
        "evidence_run_id": EVIDENCE_RUN_ID,
        "g2_probe_stage": "POST_REVIEW_PROBE",
        "git_sha": GIT_SHA,
        "gce_instance_id": INSTANCE_ID,
        "g0_g1_proof_sha256": "3" * 64,
        "g2_paper_read_only_proof_sha256": "4" * 64,
        "gateway_read_only_attestation_sha256": "5" * 64,
        "paper_account_fingerprints": [ACCOUNT],
        "g2_evidence_age_seconds": 10.0,
        "g2_snapshot_age_seconds": 10.5,
        "g2_snapshot_completion_age_seconds": 10.25,
        "independent_source_review_required": True,
        **runtime_permissions(),
        "next_gate": (
            "REBASE_AND_REVIEW_BROKER_ADAPTER_SOURCE_AGAINST_G8_12"
        ),
    }


def source():
    return SKELETON_PATH.read_text(
        encoding="utf-8"
    )


def source_review():
    value = evaluate_adapter_source_review(
        prerequisite(),
        source(),
        GIT_SHA,
        True,
        now=NOW,
    )
    assert (
        value["status"]
        == "SOURCE_POLICY_VALIDATED_NON_EXECUTABLE"
    )
    return value


def handoff():
    value = evaluate_source_review_handoff(
        source_review(),
        source(),
        GIT_SHA,
        True,
        now=NOW,
    )
    assert (
        value["status"]
        == "READY_FOR_INDEPENDENT_ADAPTER_SOURCE_REVIEW"
    )
    return value


def policy():
    return {
        "policy_version": 1,
        "reviewer_id": REVIEWER,
        "public_key_sha256": hashlib.sha256(
            PUBLIC_KEY
        ).hexdigest(),
        "expected_skeleton_version": (
            "AURORA_G8_13_IBKR_PAPER_ADAPTER_REVIEW_SKELETON_V1"
        ),
        "expected_adapter_class": (
            "IBKRPaperAdapterReviewSkeleton"
        ),
        "max_attestation_age_seconds": 1800,
        "allowed_clock_skew_seconds": 60,
    }


def artifact():
    package = handoff()
    template = package[
        "unsigned_attestation_template"
    ]
    return {
        **template,
        "review_id": REVIEW_ID,
        "decision": "ATTESTED",
        "reviewer_id": REVIEWER,
        "captured_at_utc": (
            NOW - timedelta(seconds=30)
        ).isoformat(),
        "expires_at_utc": (
            NOW + timedelta(minutes=10)
        ).isoformat(),
        "reviewer_confirms_source_non_executable": True,
        "reviewer_confirms_scope_frozen": True,
        "reviewer_evidence_sha256": "6" * 64,
        "signature_b64": base64.b64encode(
            b"s" * 64
        ).decode("ascii"),
    }


class SourceAttestationTests(unittest.TestCase):
    def evaluate(
        self,
        artifact_value=None,
        policy_value=None,
        public_key=PUBLIC_KEY,
        signature_valid=True,
        handoff_value=None,
        review_value=None,
        source_text=None,
        git_sha=GIT_SHA,
        repository_clean=True,
        now=NOW,
    ):
        return evaluate_source_attestation(
            (
                artifact_value
                if artifact_value is not None
                else artifact()
            ),
            (
                policy_value
                if policy_value is not None
                else policy()
            ),
            public_key,
            signature_valid,
            (
                handoff_value
                if handoff_value is not None
                else handoff()
            ),
            (
                review_value
                if review_value is not None
                else source_review()
            ),
            (
                source_text
                if source_text is not None
                else source()
            ),
            git_sha,
            repository_clean,
            now=now,
        )

    def assert_permissions_false(self, result):
        for name in runtime_permissions():
            self.assertIs(
                result[name],
                False,
            )

    def test_valid_independent_attestation_verifies_without_enabling_execution(self):
        result = self.evaluate()

        self.assertEqual(
            result["status"],
            "VERIFIED",
        )
        self.assertTrue(
            result["verified"]
        )
        self.assertTrue(
            result[
                "adapter_source_independently_attested"
            ]
        )
        self.assertTrue(
            result["checks"]["g2_probe_stage_bound"]
        )
        self.assertEqual(
            result["review_id"],
            REVIEW_ID,
        )
        self.assertEqual(
            result["reviewer_id"],
            REVIEWER,
        )
        self.assertEqual(
            result["git_sha"],
            GIT_SHA,
        )
        self.assertEqual(
            len(result["source_attestation_sha256"]),
            64,
        )
        self.assertEqual(
            result["next_gate"],
            "NON_EXECUTABLE_ADAPTER_IMPLEMENTATION_DESIGN_REVIEW_REQUIRED",
        )
        self.assertTrue(
            all(
                result["checks"].values()
            )
        )
        self.assert_permissions_false(
            result
        )

    def test_pre_review_probe_stage_blocks_attestation(self):
        review = source_review()
        review["g2_probe_stage"] = "PRE_REVIEW_DIAGNOSTIC"
        result = self.evaluate(
            review_value=review,
        )
        self.assertEqual(result["status"], "BLOCKED")

    def test_unsigned_handoff_template_cannot_verify(self):
        package = handoff()
        result = self.evaluate(
            artifact_value=package[
                "unsigned_attestation_template"
            ],
        )

        self.assertEqual(
            result["status"],
            "BLOCKED",
        )
        self.assertFalse(
            result["verified"]
        )
        self.assertFalse(
            result["checks"]["decision_attested"]
        )
        self.assertFalse(
            result["checks"]["review_id_uuid4"]
        )
        self.assert_permissions_false(
            result
        )

    def test_invalid_signature_or_key_binding_blocks(self):
        result = self.evaluate(
            signature_valid=False
        )
        self.assertEqual(
            result["status"],
            "BLOCKED",
        )
        self.assertFalse(
            result["checks"]["ed25519_signature_valid"]
        )

        bad_policy = policy()
        bad_policy["public_key_sha256"] = "f" * 64
        result = self.evaluate(
            policy_value=bad_policy
        )
        self.assertEqual(
            result["status"],
            "BLOCKED",
        )
        self.assertFalse(
            result["checks"]["public_key_matches_policy"]
        )

    def test_reviewer_identity_or_confirmation_tamper_blocks(self):
        value = artifact()
        value["reviewer_id"] = "wrong-reviewer"
        result = self.evaluate(
            artifact_value=value
        )
        self.assertEqual(
            result["status"],
            "BLOCKED",
        )
        self.assertFalse(
            result["checks"]["reviewer_matches_policy"]
        )

        value = artifact()
        value[
            "reviewer_confirms_source_non_executable"
        ] = False
        result = self.evaluate(
            artifact_value=value
        )
        self.assertEqual(
            result["status"],
            "BLOCKED",
        )
        self.assertFalse(
            result["checks"][
                "reviewer_confirms_source_non_executable"
            ]
        )

        value = artifact()
        value[
            "reviewer_confirms_scope_frozen"
        ] = False
        result = self.evaluate(
            artifact_value=value
        )
        self.assertEqual(
            result["status"],
            "BLOCKED",
        )

    def test_source_handoff_and_source_review_tamper_block(self):
        result = self.evaluate(
            source_text=source() + "\n# changed\n"
        )
        self.assertEqual(
            result["status"],
            "BLOCKED",
        )
        self.assertFalse(
            result["checks"]["source_sha256_bound"]
        )

        changed_handoff = handoff()
        changed_handoff[
            "review_request_sha256"
        ] = "f" * 64
        result = self.evaluate(
            handoff_value=changed_handoff
        )
        self.assertEqual(
            result["status"],
            "BLOCKED",
        )
        self.assertFalse(
            result["checks"][
                "review_request_digest_bound"
            ]
        )

        changed_review = source_review()
        changed_review[
            "runtime_prerequisite_sha256"
        ] = "f" * 64
        result = self.evaluate(
            review_value=changed_review
        )
        self.assertEqual(
            result["status"],
            "BLOCKED",
        )
        self.assertFalse(
            result["checks"][
                "source_review_artifact_digest_bound"
            ]
        )

    def test_extra_field_raw_account_injection_blocks_without_leak(self):
        value = artifact()
        value["raw_account_id"] = "DU1234567"

        result = self.evaluate(
            artifact_value=value
        )

        self.assertEqual(
            result["status"],
            "BLOCKED",
        )
        self.assertFalse(
            result["checks"]["artifact_field_set_exact"]
        )
        self.assertNotIn(
            "DU1234567",
            json.dumps(
                result,
                sort_keys=True,
            ),
        )

    def test_expired_future_git_mismatch_and_dirty_repo_block(self):
        value = artifact()
        value["expires_at_utc"] = (
            NOW - timedelta(seconds=1)
        ).isoformat()
        result = self.evaluate(
            artifact_value=value
        )
        self.assertEqual(
            result["status"],
            "BLOCKED",
        )
        self.assertFalse(
            result["checks"]["attestation_not_expired"]
        )

        value = artifact()
        value["captured_at_utc"] = (
            NOW + timedelta(minutes=5)
        ).isoformat()
        value["expires_at_utc"] = (
            NOW + timedelta(minutes=10)
        ).isoformat()
        result = self.evaluate(
            artifact_value=value
        )
        self.assertEqual(
            result["status"],
            "BLOCKED",
        )
        self.assertFalse(
            result["checks"]["capture_not_in_future"]
        )

        result = self.evaluate(
            git_sha="b" * 40
        )
        self.assertEqual(
            result["status"],
            "BLOCKED",
        )
        self.assertFalse(
            result["checks"]["git_sha_bound"]
        )

        result = self.evaluate(
            repository_clean=False
        )
        self.assertEqual(
            result["status"],
            "BLOCKED",
        )
        self.assertFalse(
            result["checks"]["repository_clean"]
        )

    def test_signature_payload_excludes_only_signature_value(self):
        value = artifact()
        payload = canonical_signed_payload(
            value
        )
        self.assertIsInstance(
            payload,
            bytes,
        )
        decoded = json.loads(
            payload.decode("utf-8")
        )
        self.assertNotIn(
            "signature_b64",
            decoded,
        )
        for name in value:
            if name != "signature_b64":
                self.assertEqual(
                    decoded[name],
                    value[name],
                )

    def test_production_paths_are_distinct_and_fixed(self):
        self.assertEqual(
            str(cli.DEFAULT_POLICY_PATH),
            "/etc/aurora/adapter-source-review-policy.json",
        )
        self.assertEqual(
            str(cli.DEFAULT_PUBLIC_KEY_PATH),
            "/etc/aurora/adapter-source-reviewer-ed25519.pem",
        )
        self.assertEqual(
            str(cli.DEFAULT_ARTIFACT_PATH),
            "/var/lib/aurora/adapter-source-review-attestation/latest.json",
        )

    def test_verifier_source_has_no_private_key_or_signing_path(self):
        source_text = inspect.getsource(
            cli
        ).lower()
        for token in (
            "private_key",
            "private-key",
            "-----begin private key-----",
            "-sign",
            "pkeyutl -sign",
            '"decision": "attested"',
            "placeorder",
            "submit_order(",
        ):
            self.assertNotIn(
                token,
                source_text,
            )


if __name__ == "__main__":
    unittest.main()
