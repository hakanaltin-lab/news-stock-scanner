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


def completion():
    return {
        "status": "PAPER_RUNTIME_VALIDATED_SHADOW_ONLY",
        "next_gate": "MANUAL_PAPER_ORDER_AUTHORIZATION_NOT_GRANTED",
        "broker_submission_allowed": False,
        "paper_order_submission_allowed": False,
        "live_execution_allowed": False,
        "automatic_promotion_allowed": False,
    }


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
    }


def authorization(comp=None, order=None):
    comp = comp or completion()
    order = order or shadow()
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
        "live_execution_allowed": False,
        "automatic_promotion_allowed": False,
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
        self.assertEqual(
            result["next_gate"],
            "PAPER_EXECUTION_CONNECTOR_REVIEW_REQUIRED",
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
