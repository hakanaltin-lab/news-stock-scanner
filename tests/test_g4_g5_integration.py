"""G7.14 integration: real G4 shadow output must be consumable by G5."""

from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
import unittest
from unittest.mock import patch

from scripts.aurora_g4_shadow import evaluate_runtime_shadow
from engines.paper_order_authorization_gate import (
    AUTH_VERSION,
    evaluate_manual_paper_authorization,
)


EVIDENCE_RUN_ID = "11111111-1111-4111-8111-111111111111"


def digest(payload):
    return hashlib.sha256(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def market_proof(now):
    stamp = now.isoformat()
    return {
        "evidence_run_id": EVIDENCE_RUN_ID,
        "symbol": "BKR",
        "snapshot": {
            "status": "REALTIME_READY",
            "quote": {
                "symbol": "BKR",
                "source": "IBKR_REALTIME",
                "market_data_type_name": "REALTIME",
                "bid": 49.99,
                "ask": 50.01,
                "last_price": 50.0,
                "market_timestamp": stamp,
                "broker_market_timestamp_verified": True,
                "retrieved_at": stamp,
                "execution_eligible": True,
                "data_quality": "AVAILABLE",
                "data_points": 1,
            },
        },
        "broker_submission_allowed": False,
        "paper_order_submission_allowed": False,
        "live_execution_allowed": False,
        "automatic_promotion_allowed": False,
        "real_money_trading_allowed": False,
    }


def readiness(now, market):
    return {
        "evidence_run_id": EVIDENCE_RUN_ID,
        "generated_at": now.isoformat(),
        "status": "READY_FOR_CONTROLLED_DRY_RUN",
        "g3_market_data_proof_sha256": digest(market),
        "broker_submission_allowed": False,
        "paper_order_submission_allowed": False,
        "live_execution_allowed": False,
        "automatic_promotion_allowed": False,
        "real_money_trading_allowed": False,
    }


def intent():
    return {
        "symbol": "BKR",
        "asset_type": "STK",
        "action": "BUY",
        "quantity": 1,
        "order_type": "LIMIT",
        "time_in_force": "DAY",
        "limit_price": 50.0,
        "risk_approval": "APPROVED",
        "idempotency_key": "g7-14-integration-001",
    }


def completion(shadow_order):
    return {
        "status": "PAPER_RUNTIME_VALIDATED_SHADOW_ONLY",
        "next_gate": "MANUAL_PAPER_ORDER_AUTHORIZATION_NOT_GRANTED",
        "checks": {
            "g4_shadow_order_payload_valid": True,
            "g4_shadow_order_ledger_payload_bound": True,
        },
        "evidence_binding": {
            "g4_shadow_order_sha256": digest(shadow_order),
        },
        "failure_reasons": [],
        "broker_submission_allowed": False,
        "paper_order_submission_allowed": False,
        "live_execution_allowed": False,
        "automatic_promotion_allowed": False,
        "real_money_trading_allowed": False,
    }


class G4G5IntegrationTests(unittest.TestCase):
    def test_real_g4_shadow_order_passes_g5_preflight_only(self):
        now = datetime.now(timezone.utc)
        market = market_proof(now)
        ready = readiness(now, market)

        with patch.dict(
            os.environ,
            {"AURORA_RUN_MODE": "DRY_RUN"},
            clear=False,
        ):
            g4 = evaluate_runtime_shadow(
                ready,
                market,
                intent(),
                now=now,
            )

        self.assertEqual(g4["status"], "SHADOW_ACCEPTED")
        shadow = g4["shadow_order"]

        for name in (
            "broker_submission_allowed",
            "paper_order_submission_allowed",
            "live_execution_allowed",
            "automatic_promotion_allowed",
            "real_money_trading_allowed",
        ):
            self.assertIn(name, shadow)
            self.assertIs(shadow[name], False)

        comp = completion(shadow)
        auth = {
            "version": AUTH_VERSION,
            "authorization_id": "11111111-1111-4111-8111-111111111111",
            "approved": True,
            "mode": "PAPER",
            "scope": "ONE_PAPER_ORDER",
            "issued_at": (now - timedelta(seconds=1)).isoformat(),
            "expires_at": (now + timedelta(minutes=5)).isoformat(),
            "completion_status_sha256": digest(comp),
            "shadow_order_sha256": digest(shadow),
            "broker_submission_allowed": False,
            "paper_order_submission_allowed": False,
            "live_execution_allowed": False,
            "automatic_promotion_allowed": False,
            "real_money_trading_allowed": False,
        }

        result = evaluate_manual_paper_authorization(
            comp,
            shadow,
            auth,
            now=now,
        )

        self.assertEqual(
            result["status"],
            "MANUAL_PAPER_AUTHORIZATION_VALIDATED",
        )
        self.assertEqual(
            result["shadow_order_sha256"],
            digest(shadow),
        )
        for name in (
            "broker_submission_allowed",
            "paper_order_submission_allowed",
            "live_execution_allowed",
            "automatic_promotion_allowed",
            "real_money_trading_allowed",
        ):
            self.assertIs(result[name], False)

    def test_blocked_dry_run_result_cannot_be_manually_authorized(self):
        now = datetime.now(timezone.utc)
        market = market_proof(now)
        ready = readiness(now, market)

        with patch.dict(
            os.environ,
            {"AURORA_RUN_MODE": "SAFE_OFF"},
            clear=False,
        ):
            g4 = evaluate_runtime_shadow(
                ready,
                market,
                intent(),
                now=now,
            )

        self.assertEqual(g4["status"], "BLOCKED")
        self.assertNotIn("shadow_order", g4)


if __name__ == "__main__":
    unittest.main()
