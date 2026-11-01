"""Offline tests for G6.19 adapter implementation review contract."""

from datetime import datetime, timedelta, timezone
import hashlib
import json
import unittest

from engines.paper_adapter_implementation_review import (
    CONTRACT_VERSION,
    MANIFEST_VERSION,
    evaluate_adapter_implementation_review,
)
from engines.paper_adapter_review_envelope import ENVELOPE_VERSION
from engines.paper_submission_attempt_journal import JOURNAL_VERSION


NOW = datetime(2026, 11, 1, 18, 0, tzinfo=timezone.utc)


def digest(payload):
    return hashlib.sha256(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def envelope():
    order = {
        "symbol": "NVDA",
        "side": "BUY",
        "asset_type": "STK",
        "order_type": "LMT",
        "time_in_force": "DAY",
        "quantity": 2,
        "limit_price": 100.0,
    }
    expected = {
        "symbol": "NVDA",
        "side": "BUY",
        "quantity": 2,
        "limit_price": 100.0,
    }
    constraints = {
        "mode": "PAPER",
        "live_execution_allowed": False,
        "automatic_retry_allowed": False,
        "automatic_cancel_allowed": False,
        "automatic_modify_allowed": False,
        "broker_order_object_allowed": False,
        "broker_request_materialization_allowed": False,
    }
    payload = {
        "version": ENVELOPE_VERSION,
        "generated_at": (NOW - timedelta(seconds=5)).isoformat(),
        "attempt_journal_version": JOURNAL_VERSION,
        "attempt_id": "22222222-2222-4222-8222-222222222222",
        "authorization_id": "11111111-1111-4111-8111-111111111111",
        "idempotency_key": "paper-review-0001",
        "contract_sha256": "a" * 64,
        "reservation_receipt_sha256": "b" * 64,
        "intent_sha256": "c" * 64,
        "expected_order_sha256": digest(expected),
        "paper_account_evidence_token": "IBKR-EVID-ABCDEF1234567890",
        "order": order,
        "constraints": constraints,
    }
    return {
        "engine": "AURORA G6.18 Paper Adapter Review Envelope",
        "envelope_version": ENVELOPE_VERSION,
        "status": "ADAPTER_REVIEW_ENVELOPE_VALIDATED_NON_EXECUTABLE",
        "reason": "PREPARED_ATTEMPT_REVIEW_ENVELOPE_READY",
        "review_only": True,
        "broker_submission_allowed": False,
        "paper_order_submission_allowed": False,
        "live_execution_allowed": False,
        "automatic_retry_allowed": False,
        "automatic_cancel_allowed": False,
        "automatic_modify_allowed": False,
        "broker_order_object_allowed": False,
        "broker_request_materialization_allowed": False,
        **payload,
        "review_envelope_sha256": digest(payload),
        "prepared_age_seconds": 5.0,
        "next_gate": "IBKR_PAPER_ADAPTER_IMPLEMENTATION_REVIEW_REQUIRED",
    }


def manifest():
    return {
        "version": MANIFEST_VERSION,
        "broker": "IBKR",
        "api_family": "TWS_API",
        "mode": "PAPER",
        "host": "127.0.0.1",
        "port": 4002,
        "client_id": 82,
        "asset_type": "STK",
        "order_type": "LMT",
        "time_in_force": "DAY",
        "fractional_shares_supported": False,
        "short_selling_supported": False,
        "market_orders_supported": False,
        "automatic_retry_supported": False,
        "automatic_cancel_supported": False,
        "automatic_modify_supported": False,
        "live_mode_supported": False,
        "live_port_allowed": False,
        "credentials_in_repository_allowed": False,
        "raw_account_id_in_artifacts_allowed": False,
        "order_submission_implemented": False,
        "broker_order_object_implemented": False,
        "broker_request_materialization_implemented": False,
        "source_review_required": True,
        "real_paper_readonly_evidence_required": True,
        "independent_security_review_required": True,
        "explicit_paper_execution_release_required": True,
        "explicit_live_execution_release_required": True,
    }


class AdapterImplementationReviewTests(unittest.TestCase):
    def evaluate(self, env=None, spec=None, now=NOW):
        return evaluate_adapter_implementation_review(
            env if env is not None else envelope(),
            spec if spec is not None else manifest(),
            now=now,
        )

    def assert_non_executable(self, result):
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

    def test_valid_review_contract_remains_non_executable(self):
        result = self.evaluate()
        self.assertEqual(
            result["status"],
            "IMPLEMENTATION_REVIEW_CONTRACT_VALIDATED_NON_EXECUTABLE",
        )
        self.assertEqual(result["contract_version"], CONTRACT_VERSION)
        self.assertEqual(
            result["next_gate"],
            "G6_20_ADAPTER_SOURCE_POLICY_REVIEW_REQUIRED",
        )
        self.assertEqual(len(result["implementation_review_contract_sha256"]), 64)
        self.assertTrue(
            result["release_prerequisites"][
                "g6_11_real_paper_readonly_evidence_required"
            ]
        )
        self.assert_non_executable(result)

    def test_contract_is_bound_to_exact_envelope_and_manifest(self):
        result = self.evaluate()
        self.assertEqual(
            result["review_envelope_sha256"],
            envelope()["review_envelope_sha256"],
        )
        self.assertEqual(
            result["implementation_manifest_sha256"],
            digest(manifest()),
        )
        self.assertEqual(result["client_id"], 82)
        self.assertEqual(result["order"]["symbol"], "NVDA")
        self.assert_non_executable(result)

    def test_live_or_live_port_manifest_blocks(self):
        for field, value in (
            ("mode", "LIVE"),
            ("port", 4001),
            ("live_mode_supported", True),
            ("live_port_allowed", True),
        ):
            with self.subTest(field=field):
                spec = manifest()
                spec[field] = value
                result = self.evaluate(spec=spec)
                self.assertEqual(result["status"], "BLOCKED")
                self.assert_non_executable(result)

    def test_execution_implementation_flags_must_stay_false(self):
        for field in (
            "order_submission_implemented",
            "broker_order_object_implemented",
            "broker_request_materialization_implemented",
        ):
            with self.subTest(field=field):
                spec = manifest()
                spec[field] = True
                result = self.evaluate(spec=spec)
                self.assertEqual(result["status"], "BLOCKED")
                self.assert_non_executable(result)

    def test_automatic_action_capabilities_block(self):
        for field in (
            "automatic_retry_supported",
            "automatic_cancel_supported",
            "automatic_modify_supported",
        ):
            with self.subTest(field=field):
                spec = manifest()
                spec[field] = True
                result = self.evaluate(spec=spec)
                self.assertEqual(result["status"], "BLOCKED")
                self.assert_non_executable(result)

    def test_order_scope_cannot_expand(self):
        mutations = (
            ("asset_type", "FUT"),
            ("order_type", "MKT"),
            ("time_in_force", "GTC"),
            ("fractional_shares_supported", True),
            ("short_selling_supported", True),
            ("market_orders_supported", True),
        )
        for field, value in mutations:
            with self.subTest(field=field):
                spec = manifest()
                spec[field] = value
                result = self.evaluate(spec=spec)
                self.assertEqual(result["status"], "BLOCKED")
                self.assert_non_executable(result)

    def test_security_and_release_prerequisites_cannot_be_weakened(self):
        required_true = (
            "source_review_required",
            "real_paper_readonly_evidence_required",
            "independent_security_review_required",
            "explicit_paper_execution_release_required",
            "explicit_live_execution_release_required",
        )
        for field in required_true:
            with self.subTest(field=field):
                spec = manifest()
                spec[field] = False
                result = self.evaluate(spec=spec)
                self.assertEqual(result["status"], "BLOCKED")
                self.assert_non_executable(result)

        for field in (
            "credentials_in_repository_allowed",
            "raw_account_id_in_artifacts_allowed",
        ):
            with self.subTest(field=field):
                spec = manifest()
                spec[field] = True
                result = self.evaluate(spec=spec)
                self.assertEqual(result["status"], "BLOCKED")
                self.assert_non_executable(result)

    def test_manifest_exact_schema_required(self):
        extra = manifest()
        extra["extra"] = "unexpected"
        result = self.evaluate(spec=extra)
        self.assertEqual(
            result["reason"],
            "IMPLEMENTATION_MANIFEST_SCHEMA_INVALID",
        )
        self.assert_non_executable(result)

        missing = manifest()
        missing.pop("broker")
        result = self.evaluate(spec=missing)
        self.assertEqual(
            result["reason"],
            "IMPLEMENTATION_MANIFEST_SCHEMA_INVALID",
        )
        self.assert_non_executable(result)

    def test_client_id_must_be_safe_integer(self):
        for value in (-1, True, 1.5, 2147483648):
            with self.subTest(value=value):
                spec = manifest()
                spec["client_id"] = value
                result = self.evaluate(spec=spec)
                self.assertEqual(
                    result["reason"],
                    "IMPLEMENTATION_CLIENT_ID_INVALID",
                )
                self.assert_non_executable(result)

    def test_stale_or_future_review_envelope_blocks(self):
        stale = envelope()
        payload = {
            key: stale[key]
            for key in (
                "version",
                "generated_at",
                "attempt_journal_version",
                "attempt_id",
                "authorization_id",
                "idempotency_key",
                "contract_sha256",
                "reservation_receipt_sha256",
                "intent_sha256",
                "expected_order_sha256",
                "paper_account_evidence_token",
                "order",
                "constraints",
            )
        }
        payload["generated_at"] = (NOW - timedelta(seconds=31)).isoformat()
        stale.update(payload)
        stale["review_envelope_sha256"] = digest(payload)
        result = self.evaluate(env=stale)
        self.assertEqual(result["reason"], "REVIEW_ENVELOPE_STALE")
        self.assert_non_executable(result)

        future = envelope()
        payload["generated_at"] = (NOW + timedelta(seconds=1)).isoformat()
        future.update(payload)
        future["review_envelope_sha256"] = digest(payload)
        result = self.evaluate(env=future)
        self.assertEqual(result["reason"], "REVIEW_ENVELOPE_STALE")
        self.assert_non_executable(result)

    def test_tampered_envelope_digest_blocks(self):
        env = envelope()
        env["review_envelope_sha256"] = "f" * 64
        result = self.evaluate(env=env)
        self.assertEqual(
            result["reason"],
            "REVIEW_ENVELOPE_DIGEST_MISMATCH",
        )
        self.assert_non_executable(result)

    def test_tampered_order_blocks_even_if_top_digest_is_recomputed(self):
        env = envelope()
        env["order"] = dict(env["order"], order_type="MKT")
        payload = {
            key: env[key]
            for key in (
                "version",
                "generated_at",
                "attempt_journal_version",
                "attempt_id",
                "authorization_id",
                "idempotency_key",
                "contract_sha256",
                "reservation_receipt_sha256",
                "intent_sha256",
                "expected_order_sha256",
                "paper_account_evidence_token",
                "order",
                "constraints",
            )
        }
        env["review_envelope_sha256"] = digest(payload)
        result = self.evaluate(env=env)
        self.assertEqual(result["reason"], "REVIEW_ENVELOPE_ORDER_INVALID")
        self.assert_non_executable(result)

    def test_permission_tamper_blocks(self):
        env = envelope()
        env["broker_request_materialization_allowed"] = True
        result = self.evaluate(env=env)
        self.assertEqual(
            result["reason"],
            "REVIEW_ENVELOPE_PERMISSION_INVALID",
        )
        self.assert_non_executable(result)

    def test_invalid_evaluation_time_fails_closed(self):
        result = self.evaluate(now="not-a-time")
        self.assertEqual(result["reason"], "INVALID_EVALUATION_TIME")
        self.assert_non_executable(result)


if __name__ == "__main__":
    unittest.main()
