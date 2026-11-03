"""G8.25 tests for non-executable IBKR Order-object materializer design."""

from datetime import datetime, timedelta, timezone
import inspect
import json
from pathlib import Path
import unittest

from engines.ibkr_order_object_materializer_design import (
    DESIGN_ID,
    DESIGN_NEXT_GATE,
    PERMISSION_FLAGS,
    evaluate_ibkr_order_object_design,
)
from engines.offline_order_request_materializer_attestation import (
    ENGINE_VERSION as ATTESTATION_ENGINE_VERSION,
    NEXT_GATE as ATTESTATION_NEXT_GATE,
)
from scripts import g6_ibkr_order_object_materializer_design as cli


NOW = datetime(2026, 11, 3, 7, 30, tzinfo=timezone.utc)
REVIEW_ID = "55555555-5555-4555-8555-555555555555"
ROOT = Path(__file__).resolve().parents[1]
DESIGN_PATH = ROOT / "config/ibkr_order_object_materializer_design_v1.json"


def design():
    return json.loads(DESIGN_PATH.read_text(encoding="utf-8"))


def attestation():
    return {
        "engine": ATTESTATION_ENGINE_VERSION,
        "status": "VERIFIED",
        "verified": True,
        "offline_materializer_independently_attested": True,
        "reason": "INDEPENDENT_OFFLINE_MATERIALIZER_ATTESTATION_VERIFIED",
        "checks": {
            "signature_valid": True,
            "sources_bound": True,
        },
        "materializer_review_id": REVIEW_ID,
        "reviewer_id": "aurora-offline-materializer-reviewer",
        "captured_at_utc": (
            NOW - timedelta(minutes=1)
        ).isoformat(),
        "expires_at_utc": (
            NOW + timedelta(minutes=20)
        ).isoformat(),
        "review_request_sha256": "1" * 64,
        "design_sha256": "2" * 64,
        "materializer_source_sha256": "3" * 64,
        "cli_source_sha256": "4" * 64,
        "materializer_attestation_sha256": "5" * 64,
        "reviewer_evidence_sha256": "6" * 64,
        **{
            name: False
            for name in PERMISSION_FLAGS
        },
        "next_gate": ATTESTATION_NEXT_GATE,
    }


class IbkrOrderObjectMaterializerDesignTests(unittest.TestCase):
    def evaluate(self, design_value=None, attestation_value=None, now=NOW):
        return evaluate_ibkr_order_object_design(
            design_value if design_value is not None else design(),
            (
                attestation_value
                if attestation_value is not None
                else attestation()
            ),
            now=now,
        )

    def assert_permissions_false(self, result):
        for name in PERMISSION_FLAGS:
            self.assertIs(result[name], False)

    def test_valid_design_advances_only_to_independent_design_attestation(self):
        result = self.evaluate()
        self.assertEqual(
            result["status"],
            "DESIGN_VALIDATED_NON_EXECUTABLE",
        )
        self.assertTrue(result["design_validated"])
        self.assertTrue(result["materializer_attestation_verified"])
        self.assertEqual(result["materializer_review_id"], REVIEW_ID)
        self.assertEqual(len(result["design_sha256"]), 64)
        self.assertEqual(result["next_gate"], DESIGN_NEXT_GATE)
        self.assertTrue(result["independent_design_review_required"])
        self.assertTrue(result["signed_design_attestation_required"])
        self.assert_permissions_false(result)

    def test_materializer_attestation_permission_regression_blocks(self):
        value = attestation()
        value["broker_order_object_allowed"] = True
        result = self.evaluate(attestation_value=value)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(
            result["reason"],
            "MATERIALIZER_ATTESTATION_NOT_VERIFIED",
        )
        self.assert_permissions_false(result)

    def test_expired_materializer_attestation_blocks(self):
        value = attestation()
        value["expires_at_utc"] = (
            NOW - timedelta(seconds=1)
        ).isoformat()
        result = self.evaluate(attestation_value=value)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(
            result["reason"],
            "MATERIALIZER_ATTESTATION_NOT_CURRENT",
        )

    def test_design_permission_endpoint_or_transmit_change_blocks(self):
        cases = []

        enabled = design()
        enabled["broker_order_object_allowed"] = True
        cases.append(enabled)

        live_port = design()
        live_port["port"] = 4001
        cases.append(live_port)

        live_mode = design()
        live_mode["broker_mode"] = "LIVE"
        cases.append(live_mode)

        transmit = design()
        transmit["planned_order_mapping"]["transmit"] = True
        cases.append(transmit)

        import_allowed = design()
        import_allowed["ibkr_import_allowed"] = True
        cases.append(import_allowed)

        for value in cases:
            with self.subTest(value=value):
                result = self.evaluate(design_value=value)
                self.assertEqual(result["status"], "BLOCKED")
                self.assertEqual(
                    result["reason"],
                    "IBKR_ORDER_OBJECT_DESIGN_POLICY_INVALID",
                )
                self.assert_permissions_false(result)

    def test_design_field_injection_blocks_without_leaking_raw_account(self):
        value = design()
        value["raw_account_id"] = "DU1234567"
        result = self.evaluate(design_value=value)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["reason"], "DESIGN_FIELD_SET_INVALID")
        self.assertNotIn("DU1234567", json.dumps(result))

    def test_attestation_field_injection_blocks(self):
        value = attestation()
        value["unexpected"] = True
        result = self.evaluate(attestation_value=value)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(
            result["reason"],
            "MATERIALIZER_ATTESTATION_FIELD_SET_INVALID",
        )

    def test_mapping_and_design_identity_are_frozen(self):
        value = design()
        self.assertEqual(value["design_id"], DESIGN_ID)
        self.assertEqual(value["next_gate"], DESIGN_NEXT_GATE)
        self.assertEqual(
            value["planned_order_mapping"]["transmit"],
            False,
        )
        self.assertFalse(value["ibkr_import_allowed"])
        self.assertFalse(value["network_allowed"])
        self.assertFalse(value["broker_order_object_allowed"])

    def test_cli_has_no_ibkr_import_signing_or_execution_path(self):
        text = inspect.getsource(cli).lower()
        for token in (
            "import ibapi",
            "from ibapi",
            "private_key",
            "private-key",
            "pkeyutl -sign",
            "placeorder",
            "submit_order(",
            "connect(",
        ):
            self.assertNotIn(token, text)

    def test_cli_paths_are_fixed(self):
        self.assertEqual(cli.DEFAULT_DESIGN_PATH, DESIGN_PATH)
        self.assertEqual(
            cli.DEFAULT_MATERIALIZER_ATTESTATION,
            ROOT
            / "runtime/aurora_g6_offline_materializer_attestation/latest.json",
        )
        self.assertEqual(
            cli.DEFAULT_OUTPUT,
            ROOT / "runtime/aurora_g6_ibkr_order_object_design/latest.json",
        )


if __name__ == "__main__":
    unittest.main()
