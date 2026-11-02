"""G8.20 tests for non-attesting implementation-candidate review handoff."""

from datetime import datetime, timezone
import hashlib
import inspect
import json
from pathlib import Path
import unittest

from engines.paper_adapter_implementation_candidate_handoff import (
    ATTESTATION_TYPE,
    REQUEST_TYPE,
    SIGNATURE_ALGORITHM,
    evaluate_candidate_review_handoff,
)
from engines.paper_adapter_implementation_candidate_review import (
    CANDIDATE_VERSION,
    ENGINE_VERSION as CANDIDATE_ENGINE_VERSION,
    EXPECTED_CLASS,
    NEXT_GATE as CANDIDATE_NEXT_GATE,
    PERMISSION_FLAGS,
    canonical_json_sha256,
)
from scripts import g6_adapter_implementation_candidate_handoff as cli


NOW = datetime(2026, 11, 2, 18, 30, tzinfo=timezone.utc)
DESIGN_REVIEW_ID = "11111111-1111-4111-8111-111111111111"
REPO_ROOT = Path(__file__).resolve().parents[1]
CANDIDATE_PATH = (
    REPO_ROOT
    / "broker_engine/ibkr_paper_adapter_implementation_candidate.py"
)


def source():
    return CANDIDATE_PATH.read_text(
        encoding="utf-8"
    )


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
        "next_gate": CANDIDATE_NEXT_GATE,
    }


class ImplementationCandidateHandoffTests(unittest.TestCase):
    def evaluate(
        self,
        review_value=None,
        source_value=None,
    ):
        return evaluate_candidate_review_handoff(
            (
                review_value
                if review_value is not None
                else candidate_review()
            ),
            (
                source_value
                if source_value is not None
                else source()
            ),
            now=NOW,
        )

    def assert_permissions_false(self, result):
        for name in PERMISSION_FLAGS:
            self.assertIs(
                result[name],
                False,
            )

    def test_valid_handoff_is_unsigned_and_non_authorizing(self):
        result = self.evaluate()

        self.assertEqual(
            result["status"],
            "READY_FOR_INDEPENDENT_IMPLEMENTATION_CANDIDATE_REVIEW",
        )
        self.assertTrue(
            result["ready_for_independent_candidate_review"]
        )
        self.assertTrue(
            result["candidate_revalidated"]
        )
        self.assertFalse(
            result["candidate_attestation_verified"]
        )
        self.assertFalse(
            result["operator_asserts_candidate_safe"]
        )
        self.assertEqual(
            result["request_type"],
            REQUEST_TYPE,
        )
        self.assertEqual(
            len(result["candidate_review_artifact_sha256"]),
            64,
        )
        self.assertEqual(
            len(result["review_request_sha256"]),
            64,
        )
        self.assertEqual(
            result["next_gate"],
            "SIGNED_INDEPENDENT_ADAPTER_IMPLEMENTATION_CANDIDATE_ATTESTATION_REQUIRED",
        )
        self.assert_permissions_false(
            result
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
        self.assertEqual(
            template["signature_algorithm"],
            SIGNATURE_ALGORITHM,
        )
        self.assertIsNone(
            template["signature_b64"]
        )
        self.assertIsNone(
            template[
                "reviewer_confirms_candidate_non_executable"
            ]
        )

    def test_permission_regression_blocks(self):
        value = candidate_review()
        value["implementation_allowed"] = True
        result = self.evaluate(
            review_value=value
        )
        self.assertEqual(
            result["status"],
            "BLOCKED",
        )
        self.assertEqual(
            result["reason"],
            "CANDIDATE_NOT_SAFE_FOR_HANDOFF",
        )
        self.assert_permissions_false(
            result
        )

    def test_source_tamper_breaks_digest_binding(self):
        changed = source() + "\n# tamper\n"
        result = self.evaluate(
            source_value=changed
        )
        self.assertEqual(
            result["status"],
            "BLOCKED",
        )
        self.assertEqual(
            result["reason"],
            "CANDIDATE_SOURCE_DIGEST_NOT_BOUND",
        )

    def test_source_broker_enablement_blocks_before_handoff(self):
        changed = source().replace(
            'raise RuntimeError("G8_19_CONNECTION_DISABLED")',
            "return True",
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
            "CANDIDATE_BROKER_METHOD_NOT_HARD_DISABLED",
        )

    def test_binding_fields_must_be_well_formed(self):
        fields = (
            "design_attestation_sha256",
            "design_sha256",
            "design_review_id",
            "source_attestation_sha256",
            "source_git_sha",
        )
        for field in fields:
            with self.subTest(field=field):
                value = candidate_review()
                value[field] = "bad"
                result = self.evaluate(
                    review_value=value
                )
                self.assertEqual(
                    result["status"],
                    "BLOCKED",
                )
                self.assertEqual(
                    result["reason"],
                    "CANDIDATE_BINDING_INVALID",
                )

    def test_request_is_explicitly_non_attesting(self):
        result = self.evaluate()
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
            request["operator_asserts_candidate_safe"]
        )
        self.assertTrue(
            request["requires_human_candidate_review"]
        )
        self.assertTrue(
            request["signed_candidate_attestation_required"]
        )
        for name in PERMISSION_FLAGS:
            self.assertIs(
                request[name],
                False,
            )

    def test_review_artifact_digest_is_exact(self):
        result = self.evaluate()
        self.assertEqual(
            result[
                "candidate_review_artifact_sha256"
            ],
            canonical_json_sha256(
                candidate_review()
            ),
        )

    def test_raw_account_injection_blocks_without_leak(self):
        value = candidate_review()
        value["raw_account_id"] = "DU1234567"
        result = self.evaluate(
            review_value=value
        )
        self.assertEqual(
            result["status"],
            "BLOCKED",
        )
        self.assertNotIn(
            "DU1234567",
            json.dumps(
                result,
                sort_keys=True,
            ),
        )

    def test_cli_has_no_signing_or_broker_execution_path(self):
        text = inspect.getsource(
            cli
        ).lower()
        for token in (
            "private_key",
            "private-key",
            "pkeyutl -sign",
            "placeorder",
            "submit_order(",
            "connect(",
        ):
            self.assertNotIn(
                token,
                text,
            )

    def test_cli_output_path_is_fixed(self):
        self.assertEqual(
            cli.DEFAULT_OUTPUT,
            REPO_ROOT
            / "runtime/aurora_g6_implementation_candidate_handoff/latest.json",
        )


if __name__ == "__main__":
    unittest.main()
