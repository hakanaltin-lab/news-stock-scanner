"""G8.18 tests for independently signed implementation-design attestation."""

from datetime import datetime, timedelta, timezone
import base64
import hashlib
import inspect
import json
from pathlib import Path
import unittest

from engines.paper_adapter_implementation_design import (
    DESIGN_NEXT_GATE,
    ENGINE_VERSION as DESIGN_ENGINE_VERSION,
    PERMISSION_FLAGS,
    canonical_json_sha256,
)
from engines.paper_adapter_implementation_design_attestation import (
    canonical_signed_payload,
    evaluate_design_attestation,
)
from engines.paper_adapter_implementation_design_handoff import (
    evaluate_implementation_design_handoff,
)
from scripts import verify_adapter_design_attestation as cli


NOW = datetime(2026, 11, 2, 17, 0, tzinfo=timezone.utc)
SOURCE_REVIEW_ID = "11111111-1111-4111-8111-111111111111"
DESIGN_REVIEW_ID = "22222222-2222-4222-8222-222222222222"
REVIEWER = "aurora-adapter-design-reviewer"
PUBLIC_KEY = (
    b"-----BEGIN PUBLIC KEY-----\n"
    b"TEST-DESIGN-REVIEW-KEY\n"
    b"-----END PUBLIC KEY-----\n"
)
REPO_ROOT = Path(__file__).resolve().parents[1]
DESIGN_PATH = (
    REPO_ROOT
    / "config/ibkr_paper_adapter_implementation_design_v1.json"
)
SOURCE_PATH = (
    REPO_ROOT
    / "broker_engine/ibkr_paper_adapter_review_skeleton.py"
)


def design():
    return json.loads(
        DESIGN_PATH.read_text(
            encoding="utf-8"
        )
    )


def source_text():
    return SOURCE_PATH.read_text(
        encoding="utf-8"
    )


def design_review():
    source_sha = hashlib.sha256(
        source_text().encode("utf-8")
    ).hexdigest()
    return {
        "engine": DESIGN_ENGINE_VERSION,
        "status": "DESIGN_VALIDATED_NON_EXECUTABLE",
        "reason": "IMPLEMENTATION_DESIGN_REVIEW_REQUIRED",
        "design_validated": True,
        "source_attestation_verified": True,
        "source_review_id": SOURCE_REVIEW_ID,
        "source_git_sha": "a" * 40,
        "source_sha256": source_sha,
        "source_attestation_sha256": "1" * 64,
        "design_sha256": canonical_json_sha256(
            design()
        ),
        "independent_design_review_required": True,
        "signed_design_attestation_required": True,
        **{
            name: False
            for name in PERMISSION_FLAGS
        },
        "next_gate": DESIGN_NEXT_GATE,
    }


def handoff():
    value = evaluate_implementation_design_handoff(
        design_review(),
        design(),
        now=NOW - timedelta(minutes=2),
    )
    assert (
        value["status"]
        == "READY_FOR_INDEPENDENT_IMPLEMENTATION_DESIGN_REVIEW"
    )
    return value


def policy():
    return {
        "policy_version": 1,
        "reviewer_id": REVIEWER,
        "public_key_sha256": hashlib.sha256(
            PUBLIC_KEY
        ).hexdigest(),
        "expected_design_id": (
            "AURORA_G8_16_IBKR_PAPER_ADAPTER_IMPLEMENTATION_DESIGN_V1"
        ),
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
    template = handoff()[
        "unsigned_attestation_template"
    ]
    return {
        **template,
        "design_review_id": DESIGN_REVIEW_ID,
        "decision": "ATTESTED",
        "reviewer_id": REVIEWER,
        "captured_at_utc": (
            NOW - timedelta(seconds=30)
        ).isoformat(),
        "expires_at_utc": (
            NOW + timedelta(minutes=10)
        ).isoformat(),
        "reviewer_confirms_design_non_executable": True,
        "reviewer_confirms_fail_closed_defaults": True,
        "reviewer_confirms_no_credentials_or_raw_accounts": True,
        "reviewer_evidence_sha256": "2" * 64,
        "signature_b64": base64.b64encode(
            b"s" * 64
        ).decode("ascii"),
    }


class DesignAttestationTests(unittest.TestCase):
    def evaluate(
        self,
        artifact_value=None,
        policy_value=None,
        public_key=PUBLIC_KEY,
        signature_valid=True,
        handoff_value=None,
        review_value=None,
        design_value=None,
        source_value=None,
        repository_clean=True,
        now=NOW,
    ):
        return evaluate_design_attestation(
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
                else design_review()
            ),
            (
                design_value
                if design_value is not None
                else design()
            ),
            (
                source_value
                if source_value is not None
                else source_text()
            ),
            repository_clean,
            now=now,
        )

    def assert_permissions_false(self, result):
        for name in PERMISSION_FLAGS:
            self.assertIs(
                result[name],
                False,
            )

    def test_valid_independent_design_attestation_verifies_without_enabling_implementation(self):
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
                "adapter_design_independently_attested"
            ]
        )
        self.assertEqual(
            result["design_review_id"],
            DESIGN_REVIEW_ID,
        )
        self.assertEqual(
            result["reviewer_id"],
            REVIEWER,
        )
        self.assertEqual(
            len(result["design_attestation_sha256"]),
            64,
        )
        self.assertEqual(
            result["next_gate"],
            "NON_EXECUTABLE_ADAPTER_IMPLEMENTATION_CANDIDATE_REQUIRED",
        )
        self.assertTrue(
            all(
                result["checks"].values()
            )
        )
        self.assert_permissions_false(
            result
        )

    def test_unsigned_handoff_template_cannot_verify(self):
        result = self.evaluate(
            artifact_value=handoff()[
                "unsigned_attestation_template"
            ],
        )

        self.assertEqual(
            result["status"],
            "BLOCKED",
        )
        self.assertFalse(
            result["checks"]["decision_attested"]
        )
        self.assertFalse(
            result["checks"]["design_review_id_uuid4"]
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

    def test_reviewer_confirmations_are_mandatory(self):
        for field in (
            "reviewer_confirms_design_non_executable",
            "reviewer_confirms_fail_closed_defaults",
            "reviewer_confirms_no_credentials_or_raw_accounts",
        ):
            with self.subTest(field=field):
                value = artifact()
                value[field] = False
                result = self.evaluate(
                    artifact_value=value
                )
                self.assertEqual(
                    result["status"],
                    "BLOCKED",
                )
                self.assertFalse(
                    result["checks"][field]
                )

    def test_handoff_request_or_design_review_tamper_blocks(self):
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

        changed_review = design_review()
        changed_review[
            "source_attestation_sha256"
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
                "design_review_artifact_digest_bound"
            ]
        )

    def test_design_or_source_tamper_blocks(self):
        changed_design = design()
        changed_design["port"] = 4001

        result = self.evaluate(
            design_value=changed_design
        )
        self.assertEqual(
            result["status"],
            "BLOCKED",
        )
        self.assertFalse(
            result["checks"]["design_policy_safe"]
        )

        result = self.evaluate(
            source_value=source_text() + "\n# tamper\n"
        )
        self.assertEqual(
            result["status"],
            "BLOCKED",
        )
        self.assertFalse(
            result["checks"]["source_identity_bound"]
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

    def test_expired_future_and_dirty_repository_block(self):
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
            repository_clean=False
        )
        self.assertEqual(
            result["status"],
            "BLOCKED",
        )
        self.assertFalse(
            result["checks"]["repository_clean"]
        )

    def test_permission_regression_in_handoff_or_design_review_blocks(self):
        changed_handoff = handoff()
        changed_handoff[
            "implementation_allowed"
        ] = True
        result = self.evaluate(
            handoff_value=changed_handoff
        )
        self.assertEqual(
            result["status"],
            "BLOCKED",
        )
        self.assertFalse(
            result["checks"][
                "handoff_ready_and_non_authorizing"
            ]
        )

        changed_review = design_review()
        changed_review[
            "paper_order_submission_allowed"
        ] = True
        result = self.evaluate(
            review_value=changed_review
        )
        self.assertEqual(
            result["status"],
            "BLOCKED",
        )
        self.assertFalse(
            result["checks"][
                "design_review_safe_and_non_authorizing"
            ]
        )

    def test_signature_payload_excludes_only_signature(self):
        value = artifact()
        payload = canonical_signed_payload(
            value
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

    def test_production_paths_are_fixed_and_separate(self):
        self.assertEqual(
            str(cli.DEFAULT_POLICY_PATH),
            "/etc/aurora/adapter-design-review-policy.json",
        )
        self.assertEqual(
            str(cli.DEFAULT_PUBLIC_KEY_PATH),
            "/etc/aurora/adapter-design-reviewer-ed25519.pem",
        )
        self.assertEqual(
            str(cli.DEFAULT_ARTIFACT_PATH),
            "/var/lib/aurora/adapter-design-review-attestation/latest.json",
        )

    def test_cli_has_no_private_key_or_signing_path(self):
        text = inspect.getsource(
            cli
        ).lower()
        for token in (
            "private_key",
            "private-key",
            "-----begin private key-----",
            "pkeyutl -sign",
            "placeorder",
            "submit_order(",
        ):
            self.assertNotIn(
                token,
                text,
            )


if __name__ == "__main__":
    unittest.main()
