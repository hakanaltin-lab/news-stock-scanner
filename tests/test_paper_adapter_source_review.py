"""G8.13 tests for the non-executable Paper adapter source review."""

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch

from engines.paper_adapter_source_review import (
    EXPECTED_G8_12_CHECKS,
    POLICY_VERSION,
    evaluate_adapter_source_review,
)
from engines.paper_connector_review_prerequisite import (
    ENGINE_VERSION as PREREQUISITE_ENGINE_VERSION,
)
from scripts import g6_adapter_source_review as cli


NOW = datetime(2026, 11, 2, 14, 30, tzinfo=timezone.utc)
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


def safe_permissions():
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
        "git_sha": GIT_SHA,
        "gce_instance_id": INSTANCE_ID,
        "g0_g1_proof_sha256": "3" * 64,
        "g2_paper_read_only_proof_sha256": "4" * 64,
        "gateway_read_only_attestation_sha256": "5" * 64,
        "paper_account_fingerprints": [ACCOUNT],
        "g2_evidence_age_seconds": 10.0,
        "g2_snapshot_age_seconds": 10.5,
        "independent_source_review_required": True,
        **safe_permissions(),
        "next_gate": (
            "REBASE_AND_REVIEW_BROKER_ADAPTER_SOURCE_AGAINST_G8_12"
        ),
    }


def source():
    return SKELETON_PATH.read_text(
        encoding="utf-8"
    )


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


class AdapterSourceReviewTests(unittest.TestCase):
    def evaluate(
        self,
        prerequisite_value=None,
        source_value=None,
        current_git_sha=GIT_SHA,
        repository_clean=True,
        now=NOW,
    ):
        return evaluate_adapter_source_review(
            (
                prerequisite_value
                if prerequisite_value is not None
                else prerequisite()
            ),
            (
                source_value
                if source_value is not None
                else source()
            ),
            current_git_sha,
            repository_clean,
            now=now,
        )

    def assert_non_executable(self, result):
        for name in safe_permissions():
            self.assertIs(
                result[name],
                False,
            )

    def test_repository_skeleton_passes_only_to_independent_source_review(self):
        result = self.evaluate()

        self.assertEqual(
            result["status"],
            "SOURCE_POLICY_VALIDATED_NON_EXECUTABLE",
        )
        self.assertEqual(
            result["policy_version"],
            POLICY_VERSION,
        )
        self.assertTrue(
            result["source_policy_validated"]
        )
        self.assertTrue(
            result["independent_source_review_required"]
        )
        self.assertEqual(
            result["next_gate"],
            "INDEPENDENT_ADAPTER_SOURCE_REVIEW_REQUIRED",
        )
        self.assertEqual(
            result["git_sha"],
            GIT_SHA,
        )
        self.assertEqual(
            result["authorization_id"],
            AUTHORIZATION_ID,
        )
        self.assertEqual(
            result["evidence_run_id"],
            EVIDENCE_RUN_ID,
        )
        self.assertEqual(
            result["paper_account_fingerprints"],
            [ACCOUNT],
        )
        self.assertEqual(
            len(result["source_sha256"]),
            64,
        )
        self.assertEqual(
            len(result["source_policy_sha256"]),
            64,
        )
        self.assert_non_executable(
            result
        )

    def test_any_import_is_rejected(self):
        result = self.evaluate(
            source_value=(
                "import ibapi\n"
                + source()
            )
        )
        self.assertEqual(
            result["status"],
            "BLOCKED",
        )
        self.assertEqual(
            result["reason"],
            "SOURCE_IMPORTS_NOT_ALLOWED",
        )
        self.assert_non_executable(
            result
        )

    def test_connection_or_submission_method_cannot_gain_behavior(self):
        replacements = {
            'raise RuntimeError("G8_13_CONNECTION_DISABLED")':
                'return {"connected": True}',
            'raise RuntimeError("G8_13_ORDER_SUBMISSION_DISABLED")':
                'return {"submitted": True}',
            'raise RuntimeError("G8_13_ORDER_CANCELLATION_DISABLED")':
                'return {"cancelled": True}',
            'raise RuntimeError("G8_13_ORDER_MODIFICATION_DISABLED")':
                'return {"modified": True}',
        }

        for old, new in replacements.items():
            with self.subTest(old=old):
                result = self.evaluate(
                    source_value=source().replace(
                        old,
                        new,
                    )
                )
                self.assertEqual(
                    result["status"],
                    "BLOCKED",
                )
                self.assert_non_executable(
                    result
                )

    def test_method_default_expression_or_extra_method_is_rejected(self):
        changed = source().replace(
            "    def connect(self, *args, **kwargs):",
            "    def connect(self, marker=object(), *args, **kwargs):",
        )
        result = self.evaluate(
            source_value=changed
        )
        self.assertEqual(
            result["reason"],
            "SOURCE_METHOD_SIGNATURE_INVALID",
        )

        changed = source().replace(
            "    def connect(self, *args, **kwargs):",
            "    def extra_capability(self):\n"
            "        return True\n\n"
            "    def connect(self, *args, **kwargs):",
        )
        result = self.evaluate(
            source_value=changed
        )
        self.assertEqual(
            result["reason"],
            "SOURCE_METHOD_SURFACE_INVALID",
        )

    def test_describe_permissions_and_scope_are_frozen(self):
        changed = source().replace(
            '"connection_allowed": False',
            '"connection_allowed": True',
        )
        result = self.evaluate(
            source_value=changed
        )
        self.assertEqual(
            result["reason"],
            "SOURCE_DESCRIBE_INVALID",
        )

        changed = source().replace(
            '"order_type": "LMT"',
            '"order_type": "MKT"',
        )
        result = self.evaluate(
            source_value=changed
        )
        self.assertEqual(
            result["reason"],
            "SOURCE_DESCRIBE_INVALID",
        )

    def test_prerequisite_permission_or_check_regression_blocks(self):
        unsafe = prerequisite()
        unsafe["connection_allowed"] = True
        result = self.evaluate(
            prerequisite_value=unsafe
        )
        self.assertEqual(
            result["reason"],
            "G8_12_PREREQUISITE_NOT_READY_FOR_SOURCE_REVIEW",
        )

        unsafe = prerequisite()
        unsafe["checks"][
            "g2_run_mode_read_only"
        ] = False
        result = self.evaluate(
            prerequisite_value=unsafe
        )
        self.assertEqual(
            result["reason"],
            "G8_12_PREREQUISITE_NOT_READY_FOR_SOURCE_REVIEW",
        )

        unsafe = prerequisite()
        unsafe["checks"].pop(
            "g2_connector_config_exact"
        )
        result = self.evaluate(
            prerequisite_value=unsafe
        )
        self.assertEqual(
            result["reason"],
            "G8_12_PREREQUISITE_NOT_READY_FOR_SOURCE_REVIEW",
        )

    def test_git_mismatch_dirty_repo_and_stale_prerequisite_block(self):
        result = self.evaluate(
            current_git_sha="b" * 40
        )
        self.assertEqual(
            result["status"],
            "BLOCKED",
        )

        result = self.evaluate(
            repository_clean=False
        )
        self.assertEqual(
            result["status"],
            "BLOCKED",
        )

        stale = prerequisite()
        stale["generated_at"] = (
            NOW - timedelta(minutes=6)
        ).isoformat()
        result = self.evaluate(
            prerequisite_value=stale
        )
        self.assertEqual(
            result["status"],
            "BLOCKED",
        )

    def test_invalid_account_fingerprint_or_age_blocks(self):
        unsafe = prerequisite()
        unsafe["paper_account_fingerprints"] = [
            "DU1234567"
        ]
        result = self.evaluate(
            prerequisite_value=unsafe
        )
        self.assertEqual(
            result["status"],
            "BLOCKED",
        )

        unsafe = prerequisite()
        unsafe["g2_snapshot_age_seconds"] = 301
        result = self.evaluate(
            prerequisite_value=unsafe
        )
        self.assertEqual(
            result["status"],
            "BLOCKED",
        )

    def test_fixed_source_reader_matches_git_tracked_blob(self):
        tracked = cli._read_fixed_tracked_source()
        self.assertEqual(
            tracked,
            source(),
        )

    def test_cli_writes_owner_only_non_executable_review_artifact(self):
        safe_result = self.evaluate()

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            prereq = root / "g8-12.json"
            output = root / "g8-13.json"
            write_trusted(
                prereq,
                prerequisite(),
            )

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
                "evaluate_adapter_source_review",
                return_value=safe_result,
            ):
                code = cli.main([
                    "--prerequisite",
                    str(prereq),
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
                "SOURCE_POLICY_VALIDATED_NON_EXECUTABLE",
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
            self.assert_non_executable(
                payload
            )


if __name__ == "__main__":
    unittest.main()
