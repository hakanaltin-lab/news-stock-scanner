"""Offline integration tests for G6.13; no broker access or orders."""

from datetime import datetime, timedelta, timezone
import hashlib
import json
import unittest

from engines.paper_intent_preflight import validate_paper_intent
from engines.paper_order_authorization_gate import (
    AUTH_VERSION,
    evaluate_manual_paper_authorization,
)
from engines.paper_portfolio_risk import evaluate_portfolio_intent
from engines.paper_submission_contract import evaluate_paper_submission_contract


NOW = datetime(2026, 11, 1, 13, 0, tzinfo=timezone.utc)


def digest(payload):
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def intent():
    return {
        "symbol": "NVDA",
        "side": "BUY",
        "order_type": "LMT",
        "quantity": 1,
        "limit_price": 100.0,
        "idempotency_key": "paper-risk-0001",
    }


def shadow():
    return {
        "status": "SHADOW_ACCEPTED",
        "shadow_order_id": "shadow-g6-13-1",
        "idempotency_key": "paper-risk-0001",
        "symbol": "NVDA",
        "asset_type": "STK",
        "action": "BUY",
        "quantity": 1,
        "order_type": "LIMIT",
        "time_in_force": "DAY",
        "limit_price": 100.0,
        "broker_submission_allowed": False,
        "paper_order_submission_allowed": False,
        "live_execution_allowed": False,
        "automatic_promotion_allowed": False,
    }


def completion():
    return {
        "status": "PAPER_RUNTIME_VALIDATED_SHADOW_ONLY",
        "next_gate": "MANUAL_PAPER_ORDER_AUTHORIZATION_NOT_GRANTED",
        "broker_submission_allowed": False,
        "paper_order_submission_allowed": False,
        "live_execution_allowed": False,
        "automatic_promotion_allowed": False,
    }


def authorization_result(order=None, evaluated_at=None):
    order = order or shadow()
    evaluated_at = evaluated_at or (NOW - timedelta(seconds=5))
    comp = completion()
    auth = {
        "version": AUTH_VERSION,
        "authorization_id": "11111111-1111-4111-8111-111111111111",
        "approved": True,
        "mode": "PAPER",
        "scope": "ONE_PAPER_ORDER",
        "issued_at": (evaluated_at - timedelta(seconds=10)).isoformat(),
        "expires_at": (evaluated_at + timedelta(minutes=5)).isoformat(),
        "completion_status_sha256": digest(comp),
        "shadow_order_sha256": digest(order),
        "live_execution_allowed": False,
        "automatic_promotion_allowed": False,
    }
    return evaluate_manual_paper_authorization(
        comp, order, auth, now=evaluated_at
    )


def risk_result(order_intent=None):
    order_intent = order_intent or intent()
    context = {
        "mode": "PAPER",
        "live_trading_allowed": False,
        "broker_read_only": True,
        "paper_account_verified": True,
        "kill_switch_engaged": True,
        "paper_account_fingerprint": "PAPER-REDACTED",
    }
    portfolio = {
        "snapshot_verified": True,
        "snapshot_fresh": True,
        "snapshot_generated_at_utc": (NOW - timedelta(seconds=5)).isoformat(),
        "paper_account_fingerprint": "PAPER-REDACTED",
        "equity_usd": 1000,
        "gross_exposure_usd": 300,
        "pending_notional_usd": 100,
        "pending_orders": [{
            "symbol": "AMD",
            "side": "BUY",
            "quantity": 1,
            "limit_price": 100.0,
            "idempotency_key": "existing-pending-0001",
        }],
        "known_idempotency_keys": [],
    }
    return evaluate_portfolio_intent(
        order_intent, context, portfolio, now_utc=NOW
    )


class PaperSubmissionContractTests(unittest.TestCase):
    def evaluate(self, **overrides):
        values = {
            "authorization_result": authorization_result(),
            "risk_result": risk_result(),
            "intent": intent(),
            "shadow_order": shadow(),
            "consumed_authorization_ids": [],
            "now": NOW,
        }
        values.update(overrides)
        return evaluate_paper_submission_contract(**values)

    def test_valid_artifacts_remain_non_executable(self):
        result = self.evaluate()
        self.assertEqual(
            result["status"],
            "SUBMISSION_CONTRACT_VALIDATED_NON_EXECUTABLE",
        )
        self.assertFalse(result["broker_submission_allowed"])
        self.assertFalse(result["paper_order_submission_allowed"])
        self.assertFalse(result["live_execution_allowed"])
        self.assertFalse(result["automatic_promotion_allowed"])
        self.assertFalse(result["real_money_trading_allowed"])
        self.assertFalse(result["broker_order_object_allowed"])
        self.assertTrue(
            result["authorization_id_must_be_atomically_consumed_before_submission"]
        )
        self.assertEqual(
            result["next_gate"],
            "PAPER_BROKER_ADAPTER_CODE_REVIEW_REQUIRED",
        )
        self.assertEqual(len(result["contract_sha256"]), 64)

    def test_risk_artifact_is_real_g6_12_output(self):
        preflight = validate_paper_intent(
            intent(),
            {
                "mode": "PAPER",
                "live_trading_allowed": False,
                "broker_read_only": True,
                "paper_account_verified": True,
                "kill_switch_engaged": True,
            },
        )
        risk = risk_result()
        self.assertEqual(risk["intent_sha256"], preflight["intent_sha256"])
        self.assertEqual(
            self.evaluate(risk_result=risk)["status"],
            "SUBMISSION_CONTRACT_VALIDATED_NON_EXECUTABLE",
        )

    def test_modified_intent_after_risk_validation_blocks(self):
        changed = intent()
        changed["quantity"] = 2
        result = self.evaluate(intent=changed)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertFalse(result["checks"]["risk_intent_digest_bound"])

    def test_shadow_changed_after_human_authorization_blocks(self):
        reviewed = shadow()
        auth = authorization_result(reviewed)
        changed = dict(reviewed, limit_price=99.0)
        result = self.evaluate(
            authorization_result=auth,
            shadow_order=changed,
        )
        self.assertEqual(result["status"], "BLOCKED")
        self.assertFalse(
            result["checks"]["shadow_digest_bound_to_authorization"]
        )

    def test_human_can_review_wrong_shadow_but_crosscheck_still_blocks(self):
        wrong = shadow()
        wrong["quantity"] = 2
        auth = authorization_result(wrong)
        result = self.evaluate(
            authorization_result=auth,
            shadow_order=wrong,
        )
        self.assertEqual(result["status"], "BLOCKED")
        self.assertTrue(
            result["checks"]["shadow_digest_bound_to_authorization"]
        )
        self.assertFalse(
            result["checks"]["shadow_execution_fields_match_intent"]
        )

    def test_replayed_authorization_blocks(self):
        auth = authorization_result()
        result = self.evaluate(
            authorization_result=auth,
            consumed_authorization_ids=[auth["authorization_id"]],
        )
        self.assertEqual(result["status"], "BLOCKED")
        self.assertFalse(
            result["checks"]["authorization_not_previously_consumed"]
        )

    def test_missing_or_corrupt_replay_history_blocks(self):
        for history in (None, "not-a-list", ["dup", "dup"], [123]):
            with self.subTest(history=repr(history)):
                result = self.evaluate(consumed_authorization_ids=history)
                self.assertEqual(result["status"], "BLOCKED")
                self.assertFalse(result["checks"]["replay_history_valid"])

    def test_stale_authorization_result_blocks(self):
        stale_time = NOW - timedelta(minutes=3)
        auth = authorization_result(evaluated_at=stale_time)
        result = self.evaluate(authorization_result=auth)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertFalse(result["checks"]["authorization_result_fresh"])

    def test_unsafe_authorization_flag_blocks(self):
        auth = authorization_result()
        auth["paper_order_submission_allowed"] = True
        result = self.evaluate(authorization_result=auth)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertFalse(result["checks"]["authorization_validated"])

    def test_unsafe_or_modified_risk_artifact_blocks(self):
        risk = risk_result()
        risk["live_trading_allowed"] = True
        result = self.evaluate(risk_result=risk)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertFalse(result["checks"]["risk_validated_read_only"])

    def test_extra_intent_field_blocks_exact_schema(self):
        changed = intent()
        changed["comment"] = "extra"
        result = self.evaluate(intent=changed)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertFalse(result["checks"]["intent_schema_valid"])

    def test_shadow_live_like_execution_fields_block(self):
        for field, value in (
            ("asset_type", "FUT"),
            ("time_in_force", "GTC"),
            ("order_type", "MKT"),
            ("action", "SELL"),
        ):
            with self.subTest(field=field):
                wrong = shadow()
                wrong[field] = value
                auth = authorization_result(wrong)
                result = self.evaluate(
                    authorization_result=auth,
                    shadow_order=wrong,
                )
                self.assertEqual(result["status"], "BLOCKED")
                self.assertFalse(
                    result["checks"]["shadow_execution_fields_match_intent"]
                )


if __name__ == "__main__":
    unittest.main()
