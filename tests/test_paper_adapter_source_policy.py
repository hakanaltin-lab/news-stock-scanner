"""Offline tests for G6.20 adapter source policy."""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import unittest

from engines.paper_adapter_implementation_review import CONTRACT_VERSION
from engines.paper_adapter_source_policy import (
    POLICY_VERSION,
    evaluate_adapter_source_policy,
)


NOW = datetime(2026, 11, 1, 19, 0, tzinfo=timezone.utc)
REPO_ROOT = Path(__file__).resolve().parents[1]
SKELETON_PATH = (
    REPO_ROOT / "broker_engine" / "ibkr_paper_adapter_review_skeleton.py"
)


def digest(payload):
    return hashlib.sha256(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def review_contract():
    release = {
        "g6_11_real_paper_readonly_evidence_required": True,
        "independent_source_review_required": True,
        "paper_execution_release_required": True,
        "live_execution_release_required": True,
    }
    payload = {
        "version": CONTRACT_VERSION,
        "generated_at": NOW.isoformat(),
        "review_envelope_sha256": "a" * 64,
        "implementation_manifest_sha256": "b" * 64,
        "attempt_id": "22222222-2222-4222-8222-222222222222",
        "authorization_id": "11111111-1111-4111-8111-111111111111",
        "idempotency_key": "paper-source-review-0001",
        "paper_account_evidence_token": "IBKR-EVID-ABCDEF1234567890",
        "client_id": 82,
        "order": {
            "symbol": "NVDA",
            "side": "BUY",
            "asset_type": "STK",
            "order_type": "LMT",
            "time_in_force": "DAY",
            "quantity": 2,
            "limit_price": 100.0,
        },
        "release_prerequisites": release,
    }
    return {
        "engine": "AURORA G6.19 Paper Adapter Implementation Review Contract",
        "contract_version": CONTRACT_VERSION,
        "status": "IMPLEMENTATION_REVIEW_CONTRACT_VALIDATED_NON_EXECUTABLE",
        "reason": "ADAPTER_SPECIFICATION_FROZEN_FOR_REVIEW",
        "implementation_allowed": False,
        "connection_allowed": False,
        "broker_submission_allowed": False,
        "paper_order_submission_allowed": False,
        "live_execution_allowed": False,
        "automatic_retry_allowed": False,
        "automatic_cancel_allowed": False,
        "automatic_modify_allowed": False,
        "broker_order_object_allowed": False,
        "broker_request_materialization_allowed": False,
        **payload,
        "implementation_review_contract_sha256": digest(payload),
        "review_envelope_age_seconds": 5.0,
        "next_gate": "G6_20_ADAPTER_SOURCE_POLICY_REVIEW_REQUIRED",
    }


def source():
    return SKELETON_PATH.read_text(encoding="utf-8")


class AdapterSourcePolicyTests(unittest.TestCase):
    def assert_safe(self, result):
        self.assertFalse(result["implementation_allowed"])
        self.assertFalse(result["connection_allowed"])
        self.assertFalse(result["broker_submission_allowed"])
        self.assertFalse(result["paper_order_submission_allowed"])
        self.assertFalse(result["live_execution_allowed"])
        self.assertFalse(result["automatic_retry_allowed"])
        self.assertFalse(result["automatic_cancel_allowed"])
        self.assertFalse(result["automatic_modify_allowed"])
        self.assertFalse(result["broker_order_object_allowed"])
        self.assertFalse(result["broker_request_materialization_allowed"])

    def test_repository_skeleton_passes_source_policy_non_executable(self):
        result = evaluate_adapter_source_policy(
            review_contract(),
            source(),
        )
        self.assertEqual(
            result["status"],
            "SOURCE_POLICY_VALIDATED_NON_EXECUTABLE",
        )
        self.assertTrue(result["source_policy_validated"])
        self.assertEqual(result["version"], POLICY_VERSION)
        self.assertEqual(
            result["next_gate"],
            "G6_21_REAL_PAPER_EVIDENCE_BINDING_REQUIRED",
        )
        self.assertEqual(len(result["source_sha256"]), 64)
        self.assertEqual(len(result["source_policy_sha256"]), 64)
        self.assert_safe(result)

    def test_policy_is_bound_to_exact_g6_19_contract_digest(self):
        contract = review_contract()
        result = evaluate_adapter_source_policy(contract, source())
        self.assertEqual(
            result["review_contract_sha256"],
            contract["implementation_review_contract_sha256"],
        )
        self.assert_safe(result)

    def test_any_import_is_rejected(self):
        changed = "import ibapi\n" + source()
        result = evaluate_adapter_source_policy(
            review_contract(),
            changed,
        )
        self.assertEqual(result["reason"], "SOURCE_IMPORTS_NOT_ALLOWED")
        self.assert_safe(result)

    def test_top_level_execution_is_rejected(self):
        changed = source() + "\nprint('run')\n"
        result = evaluate_adapter_source_policy(
            review_contract(),
            changed,
        )
        self.assertEqual(
            result["reason"],
            "SOURCE_TOP_LEVEL_EXECUTION_NOT_ALLOWED",
        )
        self.assert_safe(result)

    def test_extra_adapter_method_is_rejected(self):
        changed = source().replace(
            "    def connect(self, *args, **kwargs):\n",
            "    def extra_capability(self):\n"
            "        return True\n\n"
            "    def connect(self, *args, **kwargs):\n",
        )
        result = evaluate_adapter_source_policy(
            review_contract(),
            changed,
        )
        self.assertEqual(
            result["reason"],
            "SOURCE_METHOD_SURFACE_INVALID",
        )
        self.assert_safe(result)

    def test_connect_must_remain_single_hard_disabled_raise(self):
        changed = source().replace(
            '        raise RuntimeError("G6_20_CONNECTION_DISABLED")',
            '        return {"connected": True}',
        )
        result = evaluate_adapter_source_policy(
            review_contract(),
            changed,
        )
        self.assertEqual(
            result["reason"],
            "SOURCE_CONNECT_NOT_HARD_DISABLED",
        )
        self.assert_safe(result)

    def test_materialization_submission_cancel_modify_must_remain_disabled(self):
        replacements = {
            "G6_20_REQUEST_MATERIALIZATION_DISABLED":
                'return {"request": "materialized"}',
            "G6_20_ORDER_SUBMISSION_DISABLED":
                'return {"status": "SUBMITTED"}',
            "G6_20_ORDER_CANCELLATION_DISABLED":
                'return {"status": "CANCELLED"}',
            "G6_20_ORDER_MODIFICATION_DISABLED":
                'return {"status": "MODIFIED"}',
        }
        method_reason = {
            "G6_20_REQUEST_MATERIALIZATION_DISABLED":
                "SOURCE_MATERIALIZE_ORDER_REQUEST_NOT_HARD_DISABLED",
            "G6_20_ORDER_SUBMISSION_DISABLED":
                "SOURCE_SUBMIT_ORDER_NOT_HARD_DISABLED",
            "G6_20_ORDER_CANCELLATION_DISABLED":
                "SOURCE_CANCEL_ORDER_NOT_HARD_DISABLED",
            "G6_20_ORDER_MODIFICATION_DISABLED":
                "SOURCE_MODIFY_ORDER_NOT_HARD_DISABLED",
        }
        for blocked_text, replacement in replacements.items():
            with self.subTest(blocked_text=blocked_text):
                changed = source().replace(
                    f'raise RuntimeError("{blocked_text}")',
                    replacement,
                )
                result = evaluate_adapter_source_policy(
                    review_contract(),
                    changed,
                )
                self.assertEqual(
                    result["reason"],
                    method_reason[blocked_text],
                )
                self.assert_safe(result)

    def test_describe_permissions_cannot_be_enabled(self):
        changed = source().replace(
            '"connection_allowed": False',
            '"connection_allowed": True',
        )
        result = evaluate_adapter_source_policy(
            review_contract(),
            changed,
        )
        self.assertEqual(result["reason"], "SOURCE_DESCRIBE_INVALID")
        self.assert_safe(result)

    def test_skeleton_version_cannot_change(self):
        changed = source().replace(
            "AURORA_G6_20_IBKR_PAPER_ADAPTER_REVIEW_SKELETON_V1",
            "AURORA_G6_20_UNSAFE_V2",
        )
        result = evaluate_adapter_source_policy(
            review_contract(),
            changed,
        )
        self.assertEqual(
            result["reason"],
            "SOURCE_SKELETON_VERSION_INVALID",
        )
        self.assert_safe(result)

    def test_multiple_classes_or_inheritance_are_rejected(self):
        changed = source() + "\nclass Extra:\n    pass\n"
        result = evaluate_adapter_source_policy(
            review_contract(),
            changed,
        )
        self.assertEqual(
            result["reason"],
            "SOURCE_ADAPTER_CLASS_INVALID",
        )
        self.assert_safe(result)

        changed = source().replace(
            "class IBKRPaperAdapterReviewSkeleton:",
            "class IBKRPaperAdapterReviewSkeleton(object):",
        )
        result = evaluate_adapter_source_policy(
            review_contract(),
            changed,
        )
        self.assertEqual(
            result["reason"],
            "SOURCE_ADAPTER_INHERITANCE_OR_DECORATOR_NOT_ALLOWED",
        )
        self.assert_safe(result)

    def test_async_or_dynamic_control_flow_is_rejected(self):
        changed = source().replace(
            "    def connect(self, *args, **kwargs):",
            "    async def connect(self, *args, **kwargs):",
        )
        result = evaluate_adapter_source_policy(
            review_contract(),
            changed,
        )
        self.assertEqual(
            result["reason"],
            "SOURCE_ASYNC_METHOD_NOT_ALLOWED",
        )
        self.assert_safe(result)

    def test_invalid_or_oversized_source_blocks(self):
        for value in (None, "", "not python :::"):
            with self.subTest(value=repr(value)):
                result = evaluate_adapter_source_policy(
                    review_contract(),
                    value,
                )
                self.assertEqual(result["status"], "BLOCKED")
                self.assert_safe(result)

        oversized = "x = '" + ("a" * 100_001) + "'"
        result = evaluate_adapter_source_policy(
            review_contract(),
            oversized,
        )
        self.assertEqual(result["reason"], "SOURCE_TEXT_INVALID")
        self.assert_safe(result)

    def test_g6_19_permission_tamper_blocks_before_source_review(self):
        contract = review_contract()
        contract["connection_allowed"] = True
        result = evaluate_adapter_source_policy(contract, source())
        self.assertEqual(
            result["reason"],
            "G6_19_REVIEW_CONTRACT_PERMISSION_INVALID",
        )
        self.assert_safe(result)

    def test_g6_19_digest_tamper_blocks(self):
        contract = review_contract()
        contract["implementation_review_contract_sha256"] = "f" * 64
        result = evaluate_adapter_source_policy(contract, source())
        self.assertEqual(
            result["reason"],
            "G6_19_REVIEW_CONTRACT_DIGEST_MISMATCH",
        )
        self.assert_safe(result)

    def test_g6_11_requirement_cannot_be_removed(self):
        contract = review_contract()
        contract["release_prerequisites"] = dict(
            contract["release_prerequisites"]
        )
        contract["release_prerequisites"][
            "g6_11_real_paper_readonly_evidence_required"
        ] = False
        payload = {
            "version": contract["version"],
            "generated_at": contract["generated_at"],
            "review_envelope_sha256": contract["review_envelope_sha256"],
            "implementation_manifest_sha256":
                contract["implementation_manifest_sha256"],
            "attempt_id": contract["attempt_id"],
            "authorization_id": contract["authorization_id"],
            "idempotency_key": contract["idempotency_key"],
            "paper_account_evidence_token":
                contract["paper_account_evidence_token"],
            "client_id": contract["client_id"],
            "order": contract["order"],
            "release_prerequisites": contract["release_prerequisites"],
        }
        contract["implementation_review_contract_sha256"] = digest(payload)
        result = evaluate_adapter_source_policy(contract, source())
        self.assertEqual(
            result["reason"],
            "G6_19_RELEASE_PREREQUISITES_INVALID",
        )
        self.assert_safe(result)


if __name__ == "__main__":
    unittest.main()
