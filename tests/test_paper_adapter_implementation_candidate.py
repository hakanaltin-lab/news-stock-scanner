"""G8.19 tests for the non-executable implementation candidate gate."""

from datetime import datetime, timedelta, timezone
import hashlib
import inspect
from pathlib import Path
import unittest

from engines.paper_adapter_implementation_candidate_review import (
    CANDIDATE_VERSION,
    EXPECTED_CLASS,
    NEXT_GATE,
    PERMISSION_FLAGS,
    evaluate_implementation_candidate,
    validate_candidate_source,
)
from engines.paper_adapter_implementation_design_attestation import (
    ENGINE_VERSION as DESIGN_ATTESTATION_ENGINE_VERSION,
)
from scripts import g6_adapter_implementation_candidate_review as cli


NOW = datetime(2026, 11, 2, 18, 0, tzinfo=timezone.utc)
DESIGN_REVIEW_ID = "11111111-1111-4111-8111-111111111111"
SOURCE_REVIEW_ID = "22222222-2222-4222-8222-222222222222"
REPO_ROOT = Path(__file__).resolve().parents[1]
CANDIDATE_PATH = (
    REPO_ROOT
    / "broker_engine/ibkr_paper_adapter_implementation_candidate.py"
)


def source():
    return CANDIDATE_PATH.read_text(
        encoding="utf-8"
    )


def design_attestation():
    return {
        "engine": DESIGN_ATTESTATION_ENGINE_VERSION,
        "status": "VERIFIED",
        "verified": True,
        "adapter_design_independently_attested": True,
        "reason": "INDEPENDENT_IMPLEMENTATION_DESIGN_ATTESTATION_VERIFIED",
        "checks": {
            "signature_valid": True,
            "design_bound": True,
        },
        "design_review_id": DESIGN_REVIEW_ID,
        "reviewer_id": "aurora-adapter-design-reviewer",
        "captured_at_utc": (
            NOW - timedelta(minutes=1)
        ).isoformat(),
        "expires_at_utc": (
            NOW + timedelta(minutes=20)
        ).isoformat(),
        "design_review_artifact_sha256": "1" * 64,
        "review_request_sha256": "2" * 64,
        "design_sha256": "3" * 64,
        "source_review_id": SOURCE_REVIEW_ID,
        "source_git_sha": "a" * 40,
        "source_sha256": "4" * 64,
        "source_attestation_sha256": "5" * 64,
        "design_attestation_sha256": "6" * 64,
        "reviewer_evidence_sha256": "7" * 64,
        **{
            name: False
            for name in PERMISSION_FLAGS
        },
        "next_gate": (
            "NON_EXECUTABLE_ADAPTER_IMPLEMENTATION_CANDIDATE_REQUIRED"
        ),
    }


class ImplementationCandidateTests(unittest.TestCase):
    def evaluate(
        self,
        attestation_value=None,
        source_value=None,
        now=NOW,
    ):
        return evaluate_implementation_candidate(
            (
                attestation_value
                if attestation_value is not None
                else design_attestation()
            ),
            (
                source_value
                if source_value is not None
                else source()
            ),
            now=now,
        )

    def assert_permissions_false(self, result):
        for name in PERMISSION_FLAGS:
            self.assertIs(
                result[name],
                False,
            )

    def test_valid_candidate_is_non_executable_and_requires_independent_review(self):
        result = self.evaluate()

        self.assertEqual(
            result["status"],
            "IMPLEMENTATION_CANDIDATE_VALIDATED_NON_EXECUTABLE",
        )
        self.assertTrue(
            result["candidate_validated"]
        )
        self.assertTrue(
            result["design_attestation_verified"]
        )
        self.assertEqual(
            result["candidate_version"],
            CANDIDATE_VERSION,
        )
        self.assertEqual(
            result["adapter_class"],
            EXPECTED_CLASS,
        )
        self.assertEqual(
            len(result["candidate_source_sha256"]),
            64,
        )
        self.assertEqual(
            result["next_gate"],
            NEXT_GATE,
        )
        self.assertTrue(
            result["independent_candidate_review_required"]
        )
        self.assert_permissions_false(
            result
        )

    def test_candidate_ast_is_valid_without_importing_module(self):
        valid, reason = validate_candidate_source(
            source()
        )
        self.assertTrue(valid)
        self.assertIsNone(reason)

    def test_import_or_broker_api_attribute_is_forbidden(self):
        imported = (
            "import ibapi\n"
            + source()
        )
        valid, reason = validate_candidate_source(
            imported
        )
        self.assertFalse(valid)
        self.assertEqual(
            reason,
            "CANDIDATE_IMPORTS_NOT_ALLOWED",
        )

        broker_call = source().replace(
            'raise RuntimeError("G8_19_ORDER_SUBMISSION_DISABLED")',
            "self.client.placeOrder(1, None, None)",
            1,
        )
        valid, reason = validate_candidate_source(
            broker_call
        )
        self.assertFalse(valid)
        self.assertIn(
            reason,
            {
                "CANDIDATE_BROKER_METHOD_NOT_HARD_DISABLED",
                "CANDIDATE_BROKER_API_ATTRIBUTE_FORBIDDEN",
            },
        )

    def test_each_broker_facing_method_must_remain_hard_disabled(self):
        replacements = {
            "G8_19_CONNECTION_DISABLED": "WRONG",
            "G8_19_REQUEST_MATERIALIZATION_DISABLED": "WRONG",
            "G8_19_ORDER_SUBMISSION_DISABLED": "WRONG",
            "G8_19_ORDER_CANCELLATION_DISABLED": "WRONG",
            "G8_19_ORDER_MODIFICATION_DISABLED": "WRONG",
        }

        for token, replacement in replacements.items():
            with self.subTest(token=token):
                changed = source().replace(
                    token,
                    replacement,
                    1,
                )
                valid, reason = (
                    validate_candidate_source(
                        changed
                    )
                )
                self.assertFalse(valid)
                self.assertEqual(
                    reason,
                    "CANDIDATE_BROKER_METHOD_NOT_HARD_DISABLED",
                )

    def test_candidate_describe_permission_regression_blocks(self):
        changed = source().replace(
            '"implementation_allowed": False',
            '"implementation_allowed": True',
            1,
        )
        result = self.evaluate(
            source_value=changed
        )

        self.assertEqual(
            result["status"],
            "BLOCKED",
        )
        self.assertEqual(
            result["reason"],
            "CANDIDATE_DESCRIBE_INVALID",
        )
        self.assert_permissions_false(
            result
        )

    def test_design_attestation_permission_regression_blocks(self):
        value = design_attestation()
        value[
            "paper_order_submission_allowed"
        ] = True

        result = self.evaluate(
            attestation_value=value
        )

        self.assertEqual(
            result["status"],
            "BLOCKED",
        )
        self.assertEqual(
            result["reason"],
            "DESIGN_ATTESTATION_NOT_VERIFIED",
        )
        self.assert_permissions_false(
            result
        )

    def test_expired_design_attestation_blocks(self):
        value = design_attestation()
        value["expires_at_utc"] = (
            NOW - timedelta(seconds=1)
        ).isoformat()

        result = self.evaluate(
            attestation_value=value
        )

        self.assertEqual(
            result["status"],
            "BLOCKED",
        )
        self.assertEqual(
            result["reason"],
            "DESIGN_ATTESTATION_NOT_CURRENT",
        )

    def test_attestation_schema_injection_blocks(self):
        value = design_attestation()
        value["raw_account_id"] = "DU1234567"

        result = self.evaluate(
            attestation_value=value
        )

        self.assertEqual(
            result["status"],
            "BLOCKED",
        )
        self.assertEqual(
            result["reason"],
            "DESIGN_ATTESTATION_FIELD_SET_INVALID",
        )
        self.assertNotIn(
            "DU1234567",
            str(result),
        )

    def test_candidate_source_digest_is_exact(self):
        result = self.evaluate()
        self.assertEqual(
            result["candidate_source_sha256"],
            hashlib.sha256(
                source().encode("utf-8")
            ).hexdigest(),
        )

    def test_cli_has_no_candidate_import_or_broker_execution_path(self):
        text = inspect.getsource(
            cli
        )
        self.assertNotIn(
            "import broker_engine.ibkr_paper_adapter_implementation_candidate",
            text,
        )
        lowered = text.lower()
        for token in (
            "placeorder",
            "submit_order(",
            "connect(",
            "private_key",
        ):
            self.assertNotIn(
                token,
                lowered,
            )

    def test_cli_paths_are_fixed(self):
        self.assertEqual(
            cli.DEFAULT_CANDIDATE_PATH,
            CANDIDATE_PATH,
        )
        self.assertEqual(
            cli.DEFAULT_DESIGN_ATTESTATION,
            REPO_ROOT
            / "runtime/aurora_g6_design_attestation/latest.json",
        )
        self.assertEqual(
            cli.DEFAULT_OUTPUT,
            REPO_ROOT
            / "runtime/aurora_g6_implementation_candidate/latest.json",
        )


if __name__ == "__main__":
    unittest.main()
