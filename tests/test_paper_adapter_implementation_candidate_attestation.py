"""G8.21 tests for signed independent implementation-candidate attestation."""

from datetime import datetime, timedelta, timezone
import base64
import hashlib
import inspect
import json
from pathlib import Path
import unittest

from engines.paper_adapter_implementation_candidate_attestation import (
    canonical_signed_payload,
    evaluate_candidate_attestation,
)
from engines.paper_adapter_implementation_candidate_handoff import (
    evaluate_candidate_review_handoff,
)
from engines.paper_adapter_implementation_candidate_review import (
    CANDIDATE_VERSION,
    ENGINE_VERSION as CANDIDATE_ENGINE_VERSION,
    EXPECTED_CLASS,
    PERMISSION_FLAGS,
)
from scripts import verify_adapter_candidate_attestation as cli


NOW = datetime(2026, 11, 2, 19, 0, tzinfo=timezone.utc)
DESIGN_REVIEW_ID = "11111111-1111-4111-8111-111111111111"
CANDIDATE_REVIEW_ID = "22222222-2222-4222-8222-222222222222"
REVIEWER = "aurora-adapter-candidate-reviewer"
PUBLIC_KEY = (
    b"-----BEGIN PUBLIC KEY-----\n"
    b"TEST-CANDIDATE-REVIEW-KEY\n"
    b"-----END PUBLIC KEY-----\n"
)
ROOT = Path(__file__).resolve().parents[1]
CANDIDATE_PATH = (
    ROOT
    / "broker_engine/ibkr_paper_adapter_implementation_candidate.py"
)


def source():
    return CANDIDATE_PATH.read_text(encoding="utf-8")


def candidate_review():
    return {
        "engine": CANDIDATE_ENGINE_VERSION,
        "status": "IMPLEMENTATION_CANDIDATE_VALIDATED_NON_EXECUTABLE",
        "reason": "INDEPENDENT_IMPLEMENTATION_CANDIDATE_REVIEW_REQUIRED",
        "candidate_validated": True,
        "design_attestation_verified": True,
        "candidate_version": CANDIDATE_VERSION,
        "adapter_class": EXPECTED_CLASS,
        "candidate_source_sha256": hashlib.sha256(
            source().encode("utf-8")
        ).hexdigest(),
        "design_attestation_sha256": "1" * 64,
        "design_sha256": "2" * 64,
        "design_review_id": DESIGN_REVIEW_ID,
        "source_attestation_sha256": "3" * 64,
        "source_git_sha": "a" * 40,
        "independent_candidate_review_required": True,
        **{
            name: False
            for name in PERMISSION_FLAGS
        },
        "next_gate": (
            "INDEPENDENT_ADAPTER_IMPLEMENTATION_CANDIDATE_REVIEW_REQUIRED"
        ),
    }


def handoff():
    value = evaluate_candidate_review_handoff(
        candidate_review(),
        source(),
        now=NOW - timedelta(minutes=2),
    )
    assert (
        value["status"]
        == "READY_FOR_INDEPENDENT_IMPLEMENTATION_CANDIDATE_REVIEW"
    )
    return value


def policy():
    return {
        "policy_version": 1,
        "reviewer_id": REVIEWER,
        "public_key_sha256": hashlib.sha256(PUBLIC_KEY).hexdigest(),
        "expected_candidate_version": CANDIDATE_VERSION,
        "expected_adapter_class": EXPECTED_CLASS,
        "max_attestation_age_seconds": 1800,
        "allowed_clock_skew_seconds": 60,
    }


def artifact():
    template = handoff()["unsigned_attestation_template"]
    return {
        **template,
        "candidate_review_id": CANDIDATE_REVIEW_ID,
        "decision": "ATTESTED",
        "reviewer_id": REVIEWER,
        "captured_at_utc": (
            NOW - timedelta(seconds=30)
        ).isoformat(),
        "expires_at_utc": (
            NOW + timedelta(minutes=10)
        ).isoformat(),
        "reviewer_confirms_candidate_non_executable": True,
        "reviewer_confirms_broker_methods_hard_disabled": True,
        "reviewer_confirms_no_broker_imports": True,
        "reviewer_evidence_sha256": "4" * 64,
        "signature_b64": base64.b64encode(
            b"s" * 64
        ).decode("ascii"),
    }


class CandidateAttestationTests(unittest.TestCase):
    def evaluate(
        self,
        artifact_value=None,
        policy_value=None,
        public_key=PUBLIC_KEY,
        signature_valid=True,
        handoff_value=None,
        review_value=None,
        source_value=None,
        repository_clean=True,
        now=NOW,
    ):
        return evaluate_candidate_attestation(
            artifact_value if artifact_value is not None else artifact(),
            policy_value if policy_value is not None else policy(),
            public_key,
            signature_valid,
            handoff_value if handoff_value is not None else handoff(),
            review_value if review_value is not None else candidate_review(),
            source_value if source_value is not None else source(),
            repository_clean,
            now=now,
        )

    def assert_permissions_false(self, result):
        for name in PERMISSION_FLAGS:
            self.assertIs(result[name], False)

    def test_valid_attestation_verifies_without_enabling_execution(self):
        result = self.evaluate()
        self.assertEqual(result["status"], "VERIFIED")
        self.assertTrue(result["verified"])
        self.assertTrue(
            result["adapter_candidate_independently_attested"]
        )
        self.assertEqual(
            result["candidate_review_id"],
            CANDIDATE_REVIEW_ID,
        )
        self.assertEqual(
            result["next_gate"],
            "OFFLINE_ORDER_REQUEST_MATERIALIZER_DESIGN_REQUIRED",
        )
        self.assertTrue(all(result["checks"].values()))
        self.assert_permissions_false(result)

    def test_unsigned_template_cannot_verify(self):
        result = self.evaluate(
            artifact_value=handoff()["unsigned_attestation_template"]
        )
        self.assertEqual(result["status"], "BLOCKED")
        self.assertFalse(result["checks"]["artifact_identity"])
        self.assertFalse(result["checks"]["candidate_review_id_uuid4"])

    def test_signature_and_key_mismatch_block(self):
        result = self.evaluate(signature_valid=False)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertFalse(result["checks"]["ed25519_signature_valid"])

        bad = policy()
        bad["public_key_sha256"] = "f" * 64
        result = self.evaluate(policy_value=bad)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertFalse(result["checks"]["public_key_matches_policy"])

    def test_reviewer_confirmations_are_required(self):
        for field in (
            "reviewer_confirms_candidate_non_executable",
            "reviewer_confirms_broker_methods_hard_disabled",
            "reviewer_confirms_no_broker_imports",
        ):
            with self.subTest(field=field):
                value = artifact()
                value[field] = False
                result = self.evaluate(artifact_value=value)
                self.assertEqual(result["status"], "BLOCKED")
                self.assertFalse(result["checks"][field])

    def test_candidate_source_tamper_blocks(self):
        result = self.evaluate(
            source_value=source() + "\n# tamper\n"
        )
        self.assertEqual(result["status"], "BLOCKED")
        self.assertFalse(
            result["checks"]["candidate_source_policy_and_digest_bound"]
        )

    def test_candidate_broker_enablement_blocks(self):
        changed = source().replace(
            'raise RuntimeError("G8_19_ORDER_SUBMISSION_DISABLED")',
            "return True",
            1,
        )
        result = self.evaluate(source_value=changed)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertFalse(
            result["checks"]["candidate_source_policy_and_digest_bound"]
        )

    def test_handoff_or_candidate_review_tamper_blocks(self):
        changed = handoff()
        changed["review_request_sha256"] = "f" * 64
        result = self.evaluate(handoff_value=changed)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertFalse(result["checks"]["review_request_digest_bound"])

        changed_review = candidate_review()
        changed_review["design_attestation_sha256"] = "f" * 64
        result = self.evaluate(review_value=changed_review)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertFalse(
            result["checks"]["candidate_review_artifact_digest_bound"]
        )

    def test_permission_regression_blocks(self):
        changed = candidate_review()
        changed["paper_order_submission_allowed"] = True
        result = self.evaluate(review_value=changed)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertFalse(
            result["checks"]["candidate_review_safe_and_non_authorizing"]
        )

    def test_expired_future_dirty_and_extra_field_block(self):
        value = artifact()
        value["expires_at_utc"] = (
            NOW - timedelta(seconds=1)
        ).isoformat()
        result = self.evaluate(artifact_value=value)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertFalse(result["checks"]["attestation_not_expired"])

        value = artifact()
        value["raw_account_id"] = "DU1234567"
        result = self.evaluate(artifact_value=value)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertFalse(result["checks"]["artifact_field_set_exact"])
        self.assertNotIn("DU1234567", json.dumps(result))

        result = self.evaluate(repository_clean=False)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertFalse(result["checks"]["repository_clean"])

    def test_signature_payload_excludes_only_signature(self):
        value = artifact()
        decoded = json.loads(
            canonical_signed_payload(value).decode("utf-8")
        )
        self.assertNotIn("signature_b64", decoded)
        for key, item in value.items():
            if key != "signature_b64":
                self.assertEqual(decoded[key], item)

    def test_paths_are_fixed_and_cli_has_no_signing_path(self):
        self.assertEqual(
            str(cli.DEFAULT_POLICY_PATH),
            "/etc/aurora/adapter-candidate-review-policy.json",
        )
        self.assertEqual(
            str(cli.DEFAULT_PUBLIC_KEY_PATH),
            "/etc/aurora/adapter-candidate-reviewer-ed25519.pem",
        )
        self.assertEqual(
            str(cli.DEFAULT_ARTIFACT_PATH),
            "/var/lib/aurora/adapter-candidate-review-attestation/latest.json",
        )

        text = inspect.getsource(cli).lower()
        for token in (
            "private_key",
            "private-key",
            "pkeyutl -sign",
            "placeorder",
            "submit_order(",
        ):
            self.assertNotIn(token, text)


if __name__ == "__main__":
    unittest.main()
