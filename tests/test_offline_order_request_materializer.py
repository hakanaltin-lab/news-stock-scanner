"""G8.22 tests for the pure offline order-request materializer."""

from datetime import datetime, timedelta, timezone
import inspect
import json
from pathlib import Path
import unittest

from engines.offline_order_request_materializer import (
    ENGINE_VERSION,
    NEXT_GATE,
    PERMISSION_FLAGS,
    materialize_offline_order_request,
)
from engines.paper_adapter_implementation_candidate_attestation import (
    ENGINE_VERSION as CANDIDATE_ATTESTATION_ENGINE_VERSION,
)
from scripts import build_offline_order_request_preview as cli


NOW = datetime(2026, 11, 2, 19, 30, tzinfo=timezone.utc)
ROOT = Path(__file__).resolve().parents[1]
DESIGN_PATH = (
    ROOT
    / "config/offline_order_request_materializer_design_v1.json"
)
INTENT_ID = "11111111-1111-4111-8111-111111111111"
CANDIDATE_REVIEW_ID = "22222222-2222-4222-8222-222222222222"


def design():
    return json.loads(
        DESIGN_PATH.read_text(
            encoding="utf-8"
        )
    )


def attestation():
    return {
        "engine": CANDIDATE_ATTESTATION_ENGINE_VERSION,
        "status": "VERIFIED",
        "verified": True,
        "adapter_candidate_independently_attested": True,
        "reason": "INDEPENDENT_IMPLEMENTATION_CANDIDATE_ATTESTATION_VERIFIED",
        "checks": {
            "signature_valid": True,
            "candidate_bound": True,
        },
        "candidate_review_id": CANDIDATE_REVIEW_ID,
        "reviewer_id": "aurora-adapter-candidate-reviewer",
        "captured_at_utc": (
            NOW - timedelta(minutes=1)
        ).isoformat(),
        "expires_at_utc": (
            NOW + timedelta(minutes=20)
        ).isoformat(),
        "candidate_review_artifact_sha256": "1" * 64,
        "review_request_sha256": "2" * 64,
        "candidate_source_sha256": "3" * 64,
        "candidate_attestation_sha256": "4" * 64,
        "design_attestation_sha256": "5" * 64,
        "design_sha256": "6" * 64,
        "design_review_id": (
            "33333333-3333-4333-8333-333333333333"
        ),
        "source_attestation_sha256": "7" * 64,
        "source_git_sha": "a" * 40,
        "reviewer_evidence_sha256": "8" * 64,
        **{
            name: False
            for name in PERMISSION_FLAGS
        },
        "next_gate": (
            "OFFLINE_ORDER_REQUEST_MATERIALIZER_DESIGN_REQUIRED"
        ),
    }


def buy_intent():
    return {
        "intent_id": INTENT_ID,
        "symbol": "NVDA",
        "side": "BUY",
        "quantity": 10,
        "position_quantity": 20,
        "limit_price": "123.4500",
        "order_type": "LMT",
        "time_in_force": "DAY",
        "outside_rth": False,
        "reduce_only": False,
    }


class OfflineOrderRequestMaterializerTests(unittest.TestCase):
    def evaluate(
        self,
        design_value=None,
        attestation_value=None,
        intent_value=None,
        now=NOW,
    ):
        return materialize_offline_order_request(
            design_value if design_value is not None else design(),
            attestation_value if attestation_value is not None else attestation(),
            intent_value if intent_value is not None else buy_intent(),
            now=now,
        )

    def assert_permissions_false(self, result):
        for name in PERMISSION_FLAGS:
            self.assertIs(
                result[name],
                False,
            )

    def test_valid_buy_materializes_only_offline_preview(self):
        result = self.evaluate()

        self.assertEqual(
            result["engine"],
            ENGINE_VERSION,
        )
        self.assertEqual(
            result["status"],
            "OFFLINE_ORDER_REQUEST_PREVIEW_READY",
        )
        self.assertTrue(
            result["offline_request_materialized"]
        )
        self.assertTrue(
            result["candidate_attestation_verified"]
        )
        self.assertFalse(
            result["broker_request_materialized"]
        )
        self.assertFalse(
            result["broker_order_object_created"]
        )
        self.assertFalse(
            result["network_accessed"]
        )
        self.assertFalse(
            result["transmit"]
        )
        self.assertEqual(
            result["next_gate"],
            NEXT_GATE,
        )
        self.assertEqual(
            result["request"]["limit_price"],
            "123.45",
        )
        self.assertFalse(
            result["request"]["transmit"]
        )
        self.assert_permissions_false(
            result
        )

    def test_valid_sell_requires_position_coverage_and_reduce_only(self):
        value = buy_intent()
        value.update({
            "side": "SELL",
            "quantity": 5,
            "position_quantity": 8,
            "reduce_only": True,
        })
        result = self.evaluate(
            intent_value=value
        )
        self.assertEqual(
            result["status"],
            "OFFLINE_ORDER_REQUEST_PREVIEW_READY",
        )

        value["quantity"] = 9
        result = self.evaluate(
            intent_value=value
        )
        self.assertEqual(
            result["reason"],
            "SELL_REDUCE_ONLY_POSITION_COVERAGE_REQUIRED",
        )

        value["quantity"] = 5
        value["reduce_only"] = False
        result = self.evaluate(
            intent_value=value
        )
        self.assertEqual(
            result["reason"],
            "SELL_REDUCE_ONLY_POSITION_COVERAGE_REQUIRED",
        )

    def test_fractional_market_outside_rth_and_bad_symbol_block(self):
        cases = []

        fractional = buy_intent()
        fractional["quantity"] = 1.5
        cases.append(fractional)

        market = buy_intent()
        market["order_type"] = "MKT"
        cases.append(market)

        outside = buy_intent()
        outside["outside_rth"] = True
        cases.append(outside)

        lowercase = buy_intent()
        lowercase["symbol"] = "nvda"
        cases.append(lowercase)

        for value in cases:
            with self.subTest(value=value):
                result = self.evaluate(
                    intent_value=value
                )
                self.assertEqual(
                    result["status"],
                    "BLOCKED",
                )
                self.assertEqual(
                    result["reason"],
                    "ORDER_INTENT_INVALID",
                )

    def test_buy_reduce_only_must_be_false(self):
        value = buy_intent()
        value["reduce_only"] = True
        result = self.evaluate(
            intent_value=value
        )
        self.assertEqual(
            result["reason"],
            "BUY_REDUCE_ONLY_MUST_BE_FALSE",
        )

    def test_raw_account_or_extra_field_is_rejected(self):
        value = buy_intent()
        value["raw_account_id"] = "DU1234567"
        result = self.evaluate(
            intent_value=value
        )
        self.assertEqual(
            result["reason"],
            "ORDER_INTENT_FIELD_SET_INVALID",
        )
        self.assertNotIn(
            "DU1234567",
            json.dumps(result),
        )

    def test_expired_or_permission_regressed_candidate_attestation_blocks(self):
        value = attestation()
        value["expires_at_utc"] = (
            NOW - timedelta(seconds=1)
        ).isoformat()
        result = self.evaluate(
            attestation_value=value
        )
        self.assertEqual(
            result["reason"],
            "CANDIDATE_ATTESTATION_NOT_VERIFIED",
        )

        value = attestation()
        value["broker_submission_allowed"] = True
        result = self.evaluate(
            attestation_value=value
        )
        self.assertEqual(
            result["reason"],
            "CANDIDATE_ATTESTATION_NOT_VERIFIED",
        )
        self.assert_permissions_false(
            result
        )

    def test_design_tamper_blocks(self):
        value = design()
        value["accepted_order_type"] = "MKT"
        result = self.evaluate(
            design_value=value
        )
        self.assertEqual(
            result["reason"],
            "MATERIALIZER_DESIGN_INVALID",
        )

    def test_price_validation_is_decimal_string_only(self):
        invalid_values = (
            12.34,
            "0",
            "-1",
            "1.23456",
            "nan",
            "inf",
        )
        for price in invalid_values:
            with self.subTest(price=price):
                value = buy_intent()
                value["limit_price"] = price
                result = self.evaluate(
                    intent_value=value
                )
                self.assertEqual(
                    result["status"],
                    "BLOCKED",
                )

    def test_same_input_is_deterministic(self):
        first = self.evaluate()
        second = self.evaluate()
        self.assertEqual(
            first["request"],
            second["request"],
        )
        self.assertEqual(
            first["request_sha256"],
            second["request_sha256"],
        )
        self.assertEqual(
            first["design_sha256"],
            second["design_sha256"],
        )

    def test_module_and_cli_have_no_broker_or_network_path(self):
        import engines.offline_order_request_materializer as module

        source_text = inspect.getsource(
            module
        ).lower()
        cli_text = inspect.getsource(
            cli
        ).lower()

        for text in (
            source_text,
            cli_text,
        ):
            for token in (
                "import ibapi",
                "from ibapi",
                "placeorder",
                "reqglobalcancel",
                "socket.",
                "requests.",
                "urllib.request",
                "submit_order(",
            ):
                self.assertNotIn(
                    token,
                    text,
                )

    def test_cli_fixed_paths(self):
        self.assertEqual(
            cli.DEFAULT_DESIGN_PATH,
            DESIGN_PATH,
        )
        self.assertEqual(
            cli.DEFAULT_CANDIDATE_ATTESTATION,
            ROOT
            / "runtime/aurora_g6_candidate_attestation/latest.json",
        )
        self.assertEqual(
            cli.DEFAULT_OUTPUT,
            ROOT
            / "runtime/aurora_g6_offline_order_request/latest.json",
        )


if __name__ == "__main__":
    unittest.main()
