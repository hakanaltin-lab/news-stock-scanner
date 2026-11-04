"""G8.16 tests for the non-executable adapter implementation design."""

from datetime import datetime, timedelta, timezone
import copy
import inspect
import json
from pathlib import Path
import unittest

from engines.paper_adapter_implementation_design import (
    DESIGN_ID,
    DESIGN_NEXT_GATE,
    PERMISSION_FLAGS,
    evaluate_implementation_design,
)
from engines.paper_adapter_source_attestation import (
    EXPECTED_SOURCE_ATTESTATION_CHECKS,
)
from scripts import g6_adapter_implementation_design_review as cli


NOW = datetime(2026, 11, 2, 16, 0, tzinfo=timezone.utc)
REVIEW_ID = "11111111-1111-4111-8111-111111111111"
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


def source_attestation():
    import hashlib

    source_sha = hashlib.sha256(
        source_text().encode("utf-8")
    ).hexdigest()

    return {
        "engine": "AURORA G8.15 Adapter Source Attestation Verifier",
        "status": "VERIFIED",
        "verified": True,
        "adapter_source_independently_attested": True,
        "reason": "INDEPENDENT_SOURCE_REVIEW_ATTESTATION_VERIFIED",
        "checks": {
            name: True
            for name in EXPECTED_SOURCE_ATTESTATION_CHECKS
        },
        "review_id": REVIEW_ID,
        "reviewer_id": "aurora-adapter-source-reviewer",
        "captured_at_utc": (
            NOW - timedelta(minutes=1)
        ).isoformat(),
        "expires_at_utc": (
            NOW + timedelta(minutes=20)
        ).isoformat(),
        "git_sha": "a" * 40,
        "source_review_artifact_sha256": "1" * 64,
        "review_request_sha256": "2" * 64,
        "source_sha256": source_sha,
        "source_policy_sha256": "3" * 64,
        "source_attestation_sha256": "4" * 64,
        "reviewer_evidence_sha256": "5" * 64,
        **{
            name: False
            for name in PERMISSION_FLAGS
        },
        "next_gate": (
            "NON_EXECUTABLE_ADAPTER_IMPLEMENTATION_DESIGN_REVIEW_REQUIRED"
        ),
    }


class AdapterImplementationDesignTests(unittest.TestCase):
    def evaluate(
        self,
        design_value=None,
        attestation_value=None,
        source_value=None,
        now=NOW,
    ):
        return evaluate_implementation_design(
            (
                design_value
                if design_value is not None
                else design()
            ),
            (
                attestation_value
                if attestation_value is not None
                else source_attestation()
            ),
            (
                source_value
                if source_value is not None
                else source_text()
            ),
            now=now,
        )

    def assert_permissions_false(self, result):
        for name in PERMISSION_FLAGS:
            self.assertIs(
                result[name],
                False,
            )

    def test_valid_design_advances_only_to_independent_design_attestation(self):
        result = self.evaluate()

        self.assertEqual(
            result["status"],
            "DESIGN_VALIDATED_NON_EXECUTABLE",
        )
        self.assertTrue(
            result["design_validated"]
        )
        self.assertTrue(
            result["source_attestation_verified"]
        )
        self.assertEqual(
            result["source_review_id"],
            REVIEW_ID,
        )
        self.assertEqual(
            len(result["design_sha256"]),
            64,
        )
        self.assertEqual(
            result["next_gate"],
            DESIGN_NEXT_GATE,
        )
        self.assertTrue(
            result["independent_design_review_required"]
        )
        self.assertTrue(
            result["signed_design_attestation_required"]
        )
        self.assert_permissions_false(
            result
        )

    def test_source_attestation_check_set_must_be_exact(self):
        missing = source_attestation()
        missing["checks"].pop(
            "g2_probe_stage_bound"
        )
        result = self.evaluate(
            attestation_value=missing
        )
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(
            result["reason"],
            "SOURCE_ATTESTATION_NOT_VERIFIED",
        )

        extra = source_attestation()
        extra["checks"]["fake_check"] = True
        result = self.evaluate(
            attestation_value=extra
        )
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(
            result["reason"],
            "SOURCE_ATTESTATION_NOT_VERIFIED",
        )

    def test_source_attestation_permission_regression_blocks(self):
        value = source_attestation()
        value["implementation_allowed"] = True

        result = self.evaluate(
            attestation_value=value
        )

        self.assertEqual(
            result["status"],
            "BLOCKED",
        )
        self.assertEqual(
            result["reason"],
            "SOURCE_ATTESTATION_NOT_VERIFIED",
        )
        self.assert_permissions_false(
            result
        )

    def test_expired_source_attestation_blocks(self):
        value = source_attestation()
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
            "SOURCE_ATTESTATION_NOT_CURRENT",
        )

    def test_tracked_source_change_blocks(self):
        result = self.evaluate(
            source_value=source_text() + "\n# tamper\n"
        )

        self.assertEqual(
            result["status"],
            "BLOCKED",
        )
        self.assertEqual(
            result["reason"],
            "TRACKED_SOURCE_CHANGED_AFTER_ATTESTATION",
        )

    def test_design_permission_or_endpoint_change_blocks(self):
        cases = []

        enabled = design()
        enabled["implementation_allowed"] = True
        cases.append(enabled)

        live_port = design()
        live_port["port"] = 4001
        cases.append(live_port)

        live_mode = design()
        live_mode["broker_mode"] = "LIVE"
        cases.append(live_mode)

        market_order = design()
        market_order["market_order_allowed"] = True
        cases.append(market_order)

        for value in cases:
            with self.subTest(value=value):
                result = self.evaluate(
                    design_value=value
                )
                self.assertEqual(
                    result["status"],
                    "BLOCKED",
                )
                self.assertEqual(
                    result["reason"],
                    "IMPLEMENTATION_DESIGN_POLICY_INVALID",
                )
                self.assert_permissions_false(
                    result
                )

    def test_design_field_injection_blocks_without_leaking_raw_account(self):
        value = design()
        value["raw_account_id"] = "DU1234567"

        result = self.evaluate(
            design_value=value
        )

        self.assertEqual(
            result["status"],
            "BLOCKED",
        )
        self.assertEqual(
            result["reason"],
            "DESIGN_FIELD_SET_INVALID",
        )
        self.assertNotIn(
            "DU1234567",
            json.dumps(
                result,
                sort_keys=True,
            ),
        )

    def test_source_attestation_field_injection_blocks(self):
        value = source_attestation()
        value["unexpected"] = True

        result = self.evaluate(
            attestation_value=value
        )

        self.assertEqual(
            result["status"],
            "BLOCKED",
        )
        self.assertEqual(
            result["reason"],
            "SOURCE_ATTESTATION_FIELD_SET_INVALID",
        )

    def test_design_identity_is_frozen(self):
        value = design()
        self.assertEqual(
            value["design_id"],
            DESIGN_ID,
        )
        self.assertEqual(
            value["next_gate"],
            DESIGN_NEXT_GATE,
        )
        self.assertFalse(
            value["implementation_allowed"]
        )
        self.assertFalse(
            value["connection_allowed"]
        )
        self.assertFalse(
            value["broker_submission_allowed"]
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

    def test_cli_paths_are_fixed(self):
        self.assertEqual(
            cli.DEFAULT_DESIGN_PATH,
            REPO_ROOT
            / "config/ibkr_paper_adapter_implementation_design_v1.json",
        )
        self.assertEqual(
            cli.DEFAULT_SOURCE_ATTESTATION,
            REPO_ROOT
            / "runtime/aurora_g6_source_attestation/latest.json",
        )
        self.assertEqual(
            cli.DEFAULT_OUTPUT,
            REPO_ROOT
            / "runtime/aurora_g6_implementation_design/latest.json",
        )


if __name__ == "__main__":
    unittest.main()
