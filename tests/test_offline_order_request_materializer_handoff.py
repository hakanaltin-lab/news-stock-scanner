"""G8.23 tests for non-attesting offline materializer review handoff."""

from datetime import datetime, timezone
import inspect
import json
from pathlib import Path
import unittest

from engines.offline_order_request_materializer_handoff import (
    ATTESTATION_TYPE,
    NEXT_GATE,
    REQUEST_TYPE,
    SIGNATURE_ALGORITHM,
    evaluate_materializer_review_handoff,
)
from engines.paper_adapter_implementation_candidate_review import PERMISSION_FLAGS
from scripts import g6_offline_materializer_handoff as cli


NOW = datetime(2026, 11, 3, 6, 30, tzinfo=timezone.utc)
ROOT = Path(__file__).resolve().parents[1]
DESIGN_PATH = ROOT / "config/offline_order_request_materializer_design_v1.json"
MATERIALIZER_PATH = ROOT / "engines/offline_order_request_materializer.py"
CLI_PATH = ROOT / "scripts/build_offline_order_request_preview.py"


def design():
    return json.loads(DESIGN_PATH.read_text(encoding="utf-8"))


def materializer_source():
    return MATERIALIZER_PATH.read_text(encoding="utf-8")


def cli_source():
    return CLI_PATH.read_text(encoding="utf-8")


class OfflineMaterializerHandoffTests(unittest.TestCase):
    def evaluate(self, design_value=None, materializer_value=None, cli_value=None):
        return evaluate_materializer_review_handoff(
            design_value if design_value is not None else design(),
            materializer_value if materializer_value is not None else materializer_source(),
            cli_value if cli_value is not None else cli_source(),
            now=NOW,
        )

    def assert_permissions_false(self, result):
        for name in PERMISSION_FLAGS:
            self.assertIs(result[name], False)

    def test_valid_handoff_is_unsigned_non_authorizing_and_digest_bound(self):
        result = self.evaluate()
        self.assertEqual(
            result["status"],
            "READY_FOR_INDEPENDENT_OFFLINE_MATERIALIZER_REVIEW",
        )
        self.assertTrue(result["ready_for_independent_materializer_review"])
        self.assertTrue(result["design_revalidated"])
        self.assertTrue(result["materializer_source_revalidated"])
        self.assertTrue(result["cli_source_revalidated"])
        self.assertFalse(result["operator_asserts_materializer_safe"])
        self.assertEqual(result["request_type"], REQUEST_TYPE)
        self.assertEqual(result["next_gate"], NEXT_GATE)
        self.assertEqual(len(result["design_sha256"]), 64)
        self.assertEqual(len(result["materializer_source_sha256"]), 64)
        self.assertEqual(len(result["cli_source_sha256"]), 64)
        self.assertEqual(len(result["review_request_sha256"]), 64)
        self.assert_permissions_false(result)

        template = result["unsigned_attestation_template"]
        self.assertEqual(template["attestation_type"], ATTESTATION_TYPE)
        self.assertEqual(template["decision"], "REVIEW_REQUIRED")
        self.assertEqual(template["signature_algorithm"], SIGNATURE_ALGORITHM)
        self.assertIsNone(template["signature_b64"])
        self.assertIsNone(template["reviewer_confirms_offline_only"])

    def test_design_tamper_blocks(self):
        value = design()
        value["market_order_allowed"] = True
        result = self.evaluate(design_value=value)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["reason"], "MATERIALIZER_DESIGN_INVALID")
        self.assert_permissions_false(result)

    def test_broker_import_or_call_injection_blocks(self):
        result = self.evaluate(
            materializer_value=materializer_source() + "\nimport ibapi\n"
        )
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["reason"], "BROKER_OR_NETWORK_IMPORT_FORBIDDEN")

        changed = materializer_source() + "\ndef hidden():\n    placeOrder()\n"
        result = self.evaluate(materializer_value=changed)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["reason"], "BROKER_OR_NETWORK_CALL_FORBIDDEN")

    def test_each_offline_safety_marker_must_always_be_literal_false(self):
        for marker in (
            "broker_request_materialized",
            "broker_order_object_created",
            "network_accessed",
            "transmit",
        ):
            with self.subTest(marker=marker):
                changed = materializer_source().replace(
                    f'"{marker}": False',
                    f'"{marker}": True',
                    1,
                )
                result = self.evaluate(materializer_value=changed)
                self.assertEqual(result["status"], "BLOCKED")
                self.assertEqual(
                    result["reason"],
                    "OFFLINE_SAFETY_MARKER_MISSING",
                )
                self.assert_permissions_false(result)

    def test_removed_or_nonliteral_offline_safety_marker_blocks(self):
        for replacement in (
            '"network_accessed_removed": False',
            '"network_accessed": 0',
        ):
            with self.subTest(replacement=replacement):
                changed = materializer_source().replace(
                    '"network_accessed": False',
                    replacement,
                    1,
                )
                result = self.evaluate(materializer_value=changed)
                self.assertEqual(result["status"], "BLOCKED")
                self.assertEqual(
                    result["reason"],
                    "OFFLINE_SAFETY_MARKER_MISSING",
                )
                self.assert_permissions_false(result)

    def test_cli_network_import_injection_blocks(self):
        result = self.evaluate(
            cli_value=cli_source() + "\nimport requests\n"
        )
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["reason"], "BROKER_OR_NETWORK_IMPORT_FORBIDDEN")

    def test_same_sources_produce_same_bound_digests(self):
        first = self.evaluate()
        second = self.evaluate()
        for field in (
            "design_sha256",
            "materializer_source_sha256",
            "cli_source_sha256",
        ):
            self.assertEqual(first[field], second[field])

    def test_cli_paths_fixed_and_no_signing_or_broker_path(self):
        self.assertEqual(cli.DESIGN_PATH, DESIGN_PATH)
        self.assertEqual(cli.MATERIALIZER_PATH, MATERIALIZER_PATH)
        self.assertEqual(cli.CLI_PATH, CLI_PATH)
        self.assertEqual(
            cli.DEFAULT_OUTPUT,
            ROOT / "runtime/aurora_g6_offline_materializer_handoff/latest.json",
        )

        text = inspect.getsource(cli).lower()
        for token in (
            "private_key",
            "private-key",
            "pkeyutl -sign",
            "placeorder",
            "submit_order(",
            "import ibapi",
            "from ibapi",
        ):
            self.assertNotIn(token, text)


if __name__ == "__main__":
    unittest.main()
