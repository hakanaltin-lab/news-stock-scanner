"""Safety tests for AURORA G5 manual Paper authorization preflight."""

from datetime import datetime, timedelta, timezone
import hashlib
import json
import unittest

from engines.paper_order_authorization_gate import (
    AUTH_VERSION,
    evaluate_manual_paper_authorization,
)


NOW = datetime(2026, 10, 31, 18, 0, tzinfo=timezone.utc)


def digest(payload):
    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def shadow():
    return {
        "status": "SHADOW_ACCEPTED",
        "shadow_order_id": "shadow-1",
        "symbol": "NVDA",
        "action": "BUY",
        "quantity": 1,
        "limit_price": 100.0,
        "broker_submission_allowed": False,
        "paper_order_submission_allowed": False,
        "live_execution_allowed": False,
        "automatic_promotion_allowed": False,
        "real_money_trading_allowed": False,
    }


def completion(order=None):
    order = order if order is not None else shadow()
    return {
        "status": "PAPER_RUNTIME_VALIDATED_SHADOW_ONLY",
        "next_gate": "MANUAL_PAPER_ORDER_AUTHORIZATION_NOT_GRANTED",
        "checks": {
            "g4_shadow_order_payload_valid": True,
            "g4_shadow_order_ledger_payload_bound": True,
        },
        "evidence_binding": {
            "g4_shadow_order_sha256": digest(order),
        },
        "failure_reasons": [],
        "broker_submission_allowed": False,
        "paper_order_submission_allowed": False,
        "live_execution_allowed": False,
        "automatic_promotion_allowed": False,
        "real_money_trading_allowed": False,
    }


def authorization(comp=None, order=None):
    order = order or shadow()
    comp = comp or completion(order)
    return {
        "version": AUTH_VERSION,
        "authorization_id": "11111111-1111-4111-8111-111111111111",
        "approved": True,
        "mode": "PAPER",
        "scope": "ONE_PAPER_ORDER",
        "issued_at": (NOW - timedelta(seconds=10)).isoformat(),
        "expires_at": (NOW + timedelta(minutes=5)).isoformat(),
        "completion_status_sha256": digest(comp),
        "shadow_order_sha256": digest(order),
        "broker_submission_allowed": False,
        "paper_order_submission_allowed": False,
        "live_execution_allowed": False,
        "automatic_promotion_allowed": False,
        "real_money_trading_allowed": False,
    }


class ManualPaperAuthorizationTests(unittest.TestCase):
    def test_valid_authorization_is_preflight_only(self):
        comp = completion()
        order = shadow()
        result = evaluate_manual_paper_authorization(
            comp,
            order,
            authorization(comp, order),
            now=NOW,
        )
        self.assertEqual(
            result["status"],
            "MANUAL_PAPER_AUTHORIZATION_VALIDATED",
        )
        self.assertFalse(result["broker_submission_allowed"])
        self.assertFalse(result["paper_order_submission_allowed"])
        self.assertFalse(result["live_execution_allowed"])
        self.assertFalse(result["real_money_trading_allowed"])
        self.assertTrue(
            result["checks"]["authorization_field_set_exact"]
        )
        self.assertTrue(
            result["checks"]["authorization_permissions_non_executable"]
        )
        self.assertTrue(
            result["checks"]["completion_shadow_order_digest_bound"]
        )
        self.assertEqual(
            result["authorization_issued_at"],
            (NOW - timedelta(seconds=10)).isoformat(),
        )
        self.assertEqual(
            result["authorization_expires_at"],
            (NOW + timedelta(minutes=5)).isoformat(),
        )
        self.assertEqual(
            result["next_gate"],
            "PAPER_EXECUTION_CONNECTOR_REVIEW_REQUIRED",
        )

    def test_authorization_extra_or_missing_field_blocks(self):
        comp = completion()
        order = shadow()

        extra = authorization(comp, order)
        extra["unexpected"] = "value"
        extra_result = evaluate_manual_paper_authorization(
            comp,
            order,
            extra,
            now=NOW,
        )
        self.assertEqual(extra_result["status"], "BLOCKED")
        self.assertFalse(
            extra_result["checks"]["authorization_field_set_exact"]
        )

        missing = authorization(comp, order)
        missing.pop("real_money_trading_allowed")
        missing_result = evaluate_manual_paper_authorization(
            comp,
            order,
            missing,
            now=NOW,
        )
        self.assertEqual(missing_result["status"], "BLOCKED")
        self.assertFalse(
            missing_result["checks"]["authorization_field_set_exact"]
        )
        self.assertFalse(
            missing_result["checks"][
                "authorization_permissions_non_executable"
            ]
        )

    def test_authorization_permission_regression_blocks(self):
        comp = completion()
        order = shadow()

        for name in (
            "broker_submission_allowed",
            "paper_order_submission_allowed",
            "live_execution_allowed",
            "automatic_promotion_allowed",
            "real_money_trading_allowed",
        ):
            with self.subTest(name=name):
                auth = authorization(comp, order)
                auth[name] = True
                result = evaluate_manual_paper_authorization(
                    comp,
                    order,
                    auth,
                    now=NOW,
                )
                self.assertEqual(result["status"], "BLOCKED")
                self.assertFalse(
                    result["checks"][
                        "authorization_permissions_non_executable"
                    ]
                )

    def test_missing_human_approval_blocks(self):
        comp = completion()
        order = shadow()
        auth = authorization(comp, order)
        auth["approved"] = False
        result = evaluate_manual_paper_authorization(
            comp, order, auth, now=NOW
        )
        self.assertEqual(result["status"], "BLOCKED")
        self.assertFalse(result["checks"]["explicit_human_approval"])

    def test_completion_bound_to_different_shadow_blocks(self):
        order = shadow()
        different = dict(order, symbol="AMD")
        comp = completion(different)
        auth = authorization(comp, order)

        result = evaluate_manual_paper_authorization(
            comp,
            order,
            auth,
            now=NOW,
        )

        self.assertEqual(result["status"], "BLOCKED")
        self.assertFalse(
            result["checks"]["completion_shadow_order_digest_bound"]
        )

    def test_replayed_or_modified_evidence_blocks(self):
        comp = completion()
        order = shadow()
        auth = authorization(comp, order)
        modified = dict(order, quantity=2)
        result = evaluate_manual_paper_authorization(
            comp, modified, auth, now=NOW
        )
        self.assertEqual(result["status"], "BLOCKED")
        self.assertFalse(result["checks"]["shadow_order_digest_bound"])

    def test_expired_or_overlong_authorization_blocks(self):
        comp = completion()
        order = shadow()
        auth = authorization(comp, order)
        auth["expires_at"] = (NOW - timedelta(seconds=1)).isoformat()
        result = evaluate_manual_paper_authorization(
            comp, order, auth, now=NOW
        )
        self.assertEqual(result["status"], "BLOCKED")
        self.assertFalse(result["checks"]["authorization_current"])

    def test_live_mode_or_broad_scope_blocks(self):
        comp = completion()
        order = shadow()
        auth = authorization(comp, order)
        auth["mode"] = "LIVE"
        auth["scope"] = "MULTI_ORDER"
        result = evaluate_manual_paper_authorization(
            comp, order, auth, now=NOW
        )
        self.assertEqual(result["status"], "BLOCKED")
        self.assertFalse(result["checks"]["paper_mode_only"])
        self.assertFalse(result["checks"]["single_order_scope"])

    def test_missing_real_money_permission_flag_blocks_upstream(self):
        comp = completion()
        comp.pop("real_money_trading_allowed")
        order = shadow()
        auth = authorization(comp, order)

        result = evaluate_manual_paper_authorization(
            comp,
            order,
            auth,
            now=NOW,
        )

        self.assertEqual(result["status"], "BLOCKED")
        self.assertFalse(
            result["checks"]["completion_validated_shadow_only"]
        )

        comp = completion()
        order = shadow()
        order["real_money_trading_allowed"] = True
        auth = authorization(comp, order)

        result = evaluate_manual_paper_authorization(
            comp,
            order,
            auth,
            now=NOW,
        )

        self.assertEqual(result["status"], "BLOCKED")
        self.assertFalse(
            result["checks"]["shadow_order_accepted"]
        )

    def test_unsafe_or_missing_upstream_flags_block(self):
        comp = completion()
        comp["paper_order_submission_allowed"] = True
        order = shadow()
        auth = authorization(comp, order)
        result = evaluate_manual_paper_authorization(
            comp, order, auth, now=NOW
        )
        self.assertEqual(result["status"], "BLOCKED")
        self.assertFalse(
            result["checks"]["completion_validated_shadow_only"]
        )

        comp = completion()
        del comp["automatic_promotion_allowed"]
        auth = authorization(comp, order)
        result = evaluate_manual_paper_authorization(
            comp, order, auth, now=NOW
        )
        self.assertEqual(result["status"], "BLOCKED")
        self.assertFalse(
            result["checks"]["completion_validated_shadow_only"]
        )


if __name__ == "__main__":
    unittest.main()
