"""G8.17 tests for non-attesting implementation-design handoff."""

from datetime import datetime, timezone
import copy
import inspect
import json
from pathlib import Path
import unittest

from engines.paper_adapter_implementation_design import (
    DESIGN_ID,
    DESIGN_NEXT_GATE,
    ENGINE_VERSION as DESIGN_ENGINE_VERSION,
    PERMISSION_FLAGS,
    canonical_json_sha256,
)
from engines.paper_adapter_implementation_design_handoff import (
    ATTESTATION_TYPE,
    REQUEST_TYPE,
    SIGNATURE_ALGORITHM,
    evaluate_implementation_design_handoff,
)
from scripts import g6_adapter_implementation_design_handoff as cli


NOW = datetime(2026, 11, 2, 16, 30, tzinfo=timezone.utc)
REVIEW_ID = "11111111-1111-4111-8111-111111111111"
REPO_ROOT = Path(__file__).resolve().parents[1]
DESIGN_PATH = (
    REPO_ROOT
    / "config/ibkr_paper_adapter_implementation_design_v1.json"
)


def design():
    return json.loads(
        DESIGN_PATH.read_text(
            encoding="utf-8"
        )
    )


def design_review():
    value = design()
    return {
        "engine": DESIGN_ENGINE_VERSION,
        "status": "DESIGN_VALIDATED_NON_EXECUTABLE",
        "reason": "IMPLEMENTATION_DESIGN_REVIEW_REQUIRED",
        "design_validated": True,
        "source_attestation_verified": True,
        "source_review_id": REVIEW_ID,
        "source_git_sha": "a" * 40,
        "source_sha256": "1" * 64,
        "source_attestation_sha256": "2" * 64,
        "design_sha256": canonical_json_sha256(
            value
        ),
        "independent_design_review_required": True,
        "signed_design_attestation_required": True,
        **{
            name: False
            for name in PERMISSION_FLAGS
        },
        "next_gate": DESIGN_NEXT_GATE,
    }


class AdapterImplementationDesignHandoffTests(unittest.TestCase):
    def evaluate(
        self,
        review_value=None,
        design_value=None,
    ):
        return evaluate_implementation_design_handoff(
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
            "READY_FOR_INDEPENDENT_IMPLEMENTATION_DESIGN_REVIEW",
        )
        self.assertTrue(
            result["ready_for_independent_design_review"]
        )
        self.assertTrue(
            result["design_revalidated"]
        )
        self.assertFalse(
            result["design_attestation_verified"]
        )
        self.assertFalse(
            result["operator_asserts_design_safe"]
        )
        self.assertEqual(
            result["request_type"],
            REQUEST_TYPE,
        )
        self.assertEqual(
            len(result["design_review_artifact_sha256"]),
            64,
        )
        self.assertEqual(
            len(result["review_request_sha256"]),
            64,
        )
        self.assertEqual(
            result["next_gate"],
            "SIGNED_INDEPENDENT_ADAPTER_IMPLEMENTATION_DESIGN_ATTESTATION_REQUIRED",
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
                "reviewer_confirms_design_non_executable"
            ]
        )

    def test_review_permission_regression_blocks(self):
        value = design_review()
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
            "DESIGN_NOT_SAFE_FOR_HANDOFF",
        )
        self.assert_permissions_false(
            result
        )

    def test_design_tamper_breaks_digest_binding(self):
        value = design()
        value["time_in_force"] = "GTC"

        result = self.evaluate(
            design_value=value
        )

        self.assertEqual(
            result["status"],
            "BLOCKED",
        )
        self.assertEqual(
            result["reason"],
            "DESIGN_DIGEST_NOT_BOUND",
        )

    def test_raw_account_injection_blocks_without_leak(self):
        value = design()
        value["raw_account_id"] = "DU1234567"

        result = self.evaluate(
            design_value=value
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

    def test_source_binding_must_be_well_formed(self):
        cases = []

        bad_review_id = design_review()
        bad_review_id["source_review_id"] = "bad"
        cases.append(bad_review_id)

        bad_git = design_review()
        bad_git["source_git_sha"] = "bad"
        cases.append(bad_git)

        bad_source = design_review()
        bad_source["source_sha256"] = "bad"
        cases.append(bad_source)

        bad_attestation = design_review()
        bad_attestation[
            "source_attestation_sha256"
        ] = "bad"
        cases.append(bad_attestation)

        for value in cases:
            with self.subTest(value=value):
                result = self.evaluate(
                    review_value=value
                )
                self.assertEqual(
                    result["status"],
                    "BLOCKED",
                )
                self.assertEqual(
                    result["reason"],
                    "DESIGN_SOURCE_BINDING_INVALID",
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
            request["operator_asserts_design_safe"]
        )
        self.assertTrue(
            request["requires_human_design_review"]
        )
        self.assertTrue(
            request["signed_design_attestation_required"]
        )
        for name in PERMISSION_FLAGS:
            self.assertIs(
                request[name],
                False,
            )

    def test_cli_has_no_private_key_signing_or_broker_path(self):
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
            / "runtime/aurora_g6_implementation_design_handoff/latest.json",
        )


if __name__ == "__main__":
    unittest.main()
