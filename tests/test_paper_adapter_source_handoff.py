"""G8.14 tests for independent adapter source-review handoff."""

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch

from engines.paper_adapter_source_handoff import (
    ATTESTATION_TYPE,
    REQUEST_TYPE,
    SIGNATURE_ALGORITHM,
    evaluate_source_review_handoff,
)
from engines.paper_adapter_source_review import (
    EXPECTED_G8_12_CHECKS,
    evaluate_adapter_source_review,
)
from engines.paper_connector_review_prerequisite import (
    ENGINE_VERSION as PREREQUISITE_ENGINE_VERSION,
)
from scripts import g6_adapter_source_review_handoff as cli


NOW = datetime(2026, 11, 2, 15, 0, tzinfo=timezone.utc)
GIT_SHA = "a" * 40
AUTHORIZATION_ID = "11111111-1111-4111-8111-111111111111"
EVIDENCE_RUN_ID = "22222222-2222-4222-8222-222222222222"
INSTANCE_ID = "1234567890123456789"
ACCOUNT = "IBKR-A1B2C3D4E5"
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
    result = evaluate_adapter_source_review(
        prerequisite(),
        source(),
        GIT_SHA,
        True,
        now=NOW,
    )
    assert (
        result["status"]
        == "SOURCE_POLICY_VALIDATED_NON_EXECUTABLE"
    )
    return result


class SourceReviewHandoffTests(unittest.TestCase):
    def evaluate(
        self,
        review=None,
        source_text=None,
        git_sha=GIT_SHA,
        clean=True,
        now=NOW,
    ):
        return evaluate_source_review_handoff(
            (
                review
                if review is not None
                else source_review()
            ),
            (
                source_text
                if source_text is not None
                else source()
            ),
            git_sha,
            clean,
            now=now,
        )

    def assert_permissions_false(self, result):
        for name in runtime_permissions():
            self.assertIs(
                result[name],
                False,
            )

    def test_valid_source_review_builds_non_attesting_handoff(self):
        result = self.evaluate()

        self.assertEqual(
            result["status"],
            "READY_FOR_INDEPENDENT_ADAPTER_SOURCE_REVIEW",
        )
        self.assertEqual(
            result["request_type"],
            REQUEST_TYPE,
        )
        self.assertTrue(
            result["ready_for_independent_source_review"]
        )
        self.assertTrue(
            result["source_policy_revalidated"]
        )
        self.assertFalse(
            result["source_attestation_verified"]
        )
        self.assertFalse(
            result["operator_asserts_source_safe"]
        )
        self.assertEqual(
            result["next_gate"],
            "SIGNED_INDEPENDENT_ADAPTER_SOURCE_ATTESTATION_REQUIRED",
        )
        self.assertEqual(
            len(result["source_review_artifact_sha256"]),
            64,
        )
        self.assertEqual(
            len(result["review_request_sha256"]),
            64,
        )

        request = result["review_request"]
        self.assertEqual(
            request["request_type"],
            REQUEST_TYPE,
        )
        self.assertEqual(
            request["requested_control"],
            ATTESTATION_TYPE,
        )
        self.assertFalse(
            request["operator_asserts_source_safe"]
        )
        self.assertTrue(
            request["requires_human_source_review"]
        )
        self.assertTrue(
            request["signed_source_attestation_required"]
        )
        for name in runtime_permissions():
            self.assertIs(
                request[name],
                False,
            )

        template = result[
            "unsigned_attestation_template"
        ]
        self.assertEqual(
            template["attestation_type"],
            ATTESTATION_TYPE,
        )
        self.assertEqual(
            template["decision"],
            "REVIEW_REQUIRED",
        )
        self.assertIsNone(
            template["review_id"]
        )
        self.assertIsNone(
            template["reviewer_id"]
        )
        self.assertIsNone(
            template[
                "reviewer_confirms_source_non_executable"
            ]
        )
        self.assertIsNone(
            template[
                "reviewer_confirms_scope_frozen"
            ]
        )
        self.assertIsNone(
            template["reviewer_evidence_sha256"]
        )
        self.assertEqual(
            template["signature_algorithm"],
            SIGNATURE_ALGORITHM,
        )
        self.assertIsNone(
            template["signature_b64"]
        )
        self.assert_permissions_false(
            result
        )

    def test_pre_review_probe_stage_blocks_handoff(self):
        review = source_review()
        review["g2_probe_stage"] = "PRE_REVIEW_DIAGNOSTIC"
        result = self.evaluate(review=review)
        self.assertEqual(result["status"], "BLOCKED")

    def test_changed_source_or_source_digest_blocks(self):
        changed = source() + "\n# changed\n"
        result = self.evaluate(
            source_text=changed
        )
        self.assertEqual(
            result["status"],
            "BLOCKED",
        )

        review = source_review()
        review["source_sha256"] = "f" * 64
        result = self.evaluate(
            review=review
        )
        self.assertEqual(
            result["status"],
            "BLOCKED",
        )

    def test_source_policy_digest_tamper_blocks(self):
        review = source_review()
        review["source_policy_sha256"] = "f" * 64

        result = self.evaluate(
            review=review
        )

        self.assertEqual(
            result["status"],
            "BLOCKED",
        )
        self.assertEqual(
            result["reason"],
            "SOURCE_REVIEW_ARTIFACT_NOT_SAFE_FOR_HANDOFF",
        )

    def test_permission_or_extra_field_injection_blocks(self):
        review = source_review()
        review["connection_allowed"] = True
        result = self.evaluate(
            review=review
        )
        self.assertEqual(
            result["status"],
            "BLOCKED",
        )

        review = source_review()
        review["raw_account_id"] = "DU1234567"
        result = self.evaluate(
            review=review
        )
        self.assertEqual(
            result["status"],
            "BLOCKED",
        )
        self.assertNotIn(
            "DU1234567",
            json.dumps(result),
        )

    def test_git_mismatch_dirty_repo_or_stale_review_blocks(self):
        result = self.evaluate(
            git_sha="b" * 40
        )
        self.assertEqual(
            result["status"],
            "BLOCKED",
        )

        result = self.evaluate(
            clean=False
        )
        self.assertEqual(
            result["status"],
            "BLOCKED",
        )

        review = source_review()
        review["generated_at"] = (
            NOW - timedelta(minutes=16)
        ).isoformat()
        result = self.evaluate(
            review=review
        )
        self.assertEqual(
            result["status"],
            "BLOCKED",
        )

    def test_unsigned_template_has_no_positive_review_claim(self):
        template = self.evaluate()[
            "unsigned_attestation_template"
        ]

        serialized = json.dumps(
            template,
            sort_keys=True,
        )
        self.assertNotIn(
            '"decision": "ATTESTED"',
            serialized,
        )
        self.assertNotIn(
            '"reviewer_confirms_source_non_executable": true',
            serialized,
        )
        self.assertNotIn(
            '"reviewer_confirms_scope_frozen": true',
            serialized,
        )

    def test_cli_writes_trusted_handoff_artifact(self):
        safe_result = self.evaluate()

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            review_path = root / "source-review.json"
            output = root / "handoff.json"

            review_path.write_text(
                json.dumps(
                    source_review(),
                    indent=2,
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )
            review_path.chmod(0o600)

            with patch.object(
                cli,
                "_current_git_sha",
                return_value=GIT_SHA,
            ), patch.object(
                cli,
                "_repository_is_clean",
                return_value=True,
            ), patch.object(
                cli,
                "_read_fixed_tracked_source",
                return_value=source(),
            ), patch.object(
                cli,
                "evaluate_source_review_handoff",
                return_value=safe_result,
            ):
                code = cli.main([
                    "--source-review",
                    str(review_path),
                    "--output",
                    str(output),
                ])

            self.assertEqual(
                code,
                0,
            )
            payload = json.loads(
                output.read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(
                payload["status"],
                "READY_FOR_INDEPENDENT_ADAPTER_SOURCE_REVIEW",
            )
            metadata = output.stat()
            self.assertTrue(
                stat.S_ISREG(
                    metadata.st_mode
                )
            )
            self.assertEqual(
                stat.S_IMODE(
                    metadata.st_mode
                ),
                0o600,
            )
            self.assertEqual(
                metadata.st_nlink,
                1,
            )
            self.assert_permissions_false(
                payload
            )


if __name__ == "__main__":
    unittest.main()
