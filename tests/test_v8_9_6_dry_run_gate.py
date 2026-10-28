"""AURORA V8.9.6 dry-run execution gate tests."""

from datetime import datetime, timedelta, timezone
import os
import unittest
from unittest.mock import patch

from engines.dry_run_execution_engine import DryRunExecutionEngine


def fresh_market_data(
    *,
    source="IBKR_REALTIME",
    bid=99.95,
    ask=100.05,
    last_price=100.0,
    age_seconds=0,
):
    now = datetime.now(timezone.utc)
    timestamp = now - timedelta(seconds=age_seconds)
    return {
        "source": source,
        "market_timestamp": timestamp.isoformat(),
        "last_price": last_price,
        "bid": bid,
        "ask": ask,
        "data_points": 1,
        "data_quality": "AVAILABLE",
    }


def base_intent(**overrides):
    intent = {
        "symbol": "NVDA",
        "asset_type": "STK",
        "action": "BUY",
        "quantity": 1,
        "order_type": "LIMIT",
        "time_in_force": "DAY",
        "limit_price": 100.0,
        "risk_approval": "APPROVED",
        "idempotency_key": "signal-001:NVDA:BUY",
        "current_position_qty": 0,
    }
    intent.update(overrides)
    return intent


class DryRunExecutionGateTests(unittest.TestCase):
    def setUp(self):
        self.engine = DryRunExecutionEngine()

    def test_safe_off_blocks_shadow_order(self):
        with patch.dict(os.environ, {
            "AURORA_RUN_MODE": "SAFE_OFF",
        }, clear=True):
            result = self.engine.evaluate_and_create_shadow_order(
                base_intent(),
                fresh_market_data(),
            )

        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["reason"], "DRY_RUN_MODE_REQUIRED")
        self.assertFalse(result["broker_submission_allowed"])

    def test_valid_dry_run_creates_shadow_order_only(self):
        with patch.dict(os.environ, {
            "AURORA_RUN_MODE": "DRY_RUN",
        }, clear=True):
            result = self.engine.evaluate_and_create_shadow_order(
                base_intent(),
                fresh_market_data(),
            )

        self.assertEqual(result["status"], "SHADOW_ACCEPTED")
        self.assertFalse(result["broker_submission_allowed"])
        self.assertFalse(result["paper_order_submission_allowed"])
        self.assertFalse(result["live_execution_allowed"])

    def test_duplicate_idempotency_key_is_blocked(self):
        with patch.dict(os.environ, {
            "AURORA_RUN_MODE": "DRY_RUN",
        }, clear=True):
            first = self.engine.evaluate_and_create_shadow_order(
                base_intent(),
                fresh_market_data(),
            )
            second = self.engine.evaluate_and_create_shadow_order(
                base_intent(),
                fresh_market_data(),
            )

        self.assertEqual(first["status"], "SHADOW_ACCEPTED")
        self.assertEqual(second["status"], "BLOCKED")
        self.assertEqual(second["reason"], "DUPLICATE_ORDER_INTENT")

    def test_yfinance_research_data_is_blocked(self):
        with patch.dict(os.environ, {
            "AURORA_RUN_MODE": "DRY_RUN",
        }, clear=True):
            result = self.engine.evaluate_and_create_shadow_order(
                base_intent(),
                fresh_market_data(source="YFINANCE_15M"),
            )

        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["reason"], "MARKET_DATA_GATE_BLOCKED")

    def test_stale_execution_data_is_blocked(self):
        with patch.dict(os.environ, {
            "AURORA_RUN_MODE": "DRY_RUN",
        }, clear=True):
            result = self.engine.evaluate_and_create_shadow_order(
                base_intent(),
                fresh_market_data(age_seconds=60),
            )

        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["reason"], "MARKET_DATA_GATE_BLOCKED")

    def test_market_order_is_blocked(self):
        with patch.dict(os.environ, {
            "AURORA_RUN_MODE": "DRY_RUN",
        }, clear=True):
            result = self.engine.evaluate_and_create_shadow_order(
                base_intent(order_type="MARKET"),
                fresh_market_data(),
            )

        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["reason"], "LIMIT_ORDERS_ONLY")

    def test_non_stock_asset_is_blocked(self):
        with patch.dict(os.environ, {
            "AURORA_RUN_MODE": "DRY_RUN",
        }, clear=True):
            result = self.engine.evaluate_and_create_shadow_order(
                base_intent(asset_type="OPT"),
                fresh_market_data(),
            )

        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["reason"], "STOCKS_ONLY")

    def test_short_sell_is_blocked(self):
        with patch.dict(os.environ, {
            "AURORA_RUN_MODE": "DRY_RUN",
        }, clear=True):
            result = self.engine.evaluate_and_create_shadow_order(
                base_intent(
                    action="SELL",
                    quantity=2,
                    current_position_qty=1,
                ),
                fresh_market_data(),
            )

        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["reason"], "SHORT_SELLING_DISABLED")

    def test_order_notional_limit_is_enforced(self):
        with patch.dict(os.environ, {
            "AURORA_RUN_MODE": "DRY_RUN",
            "AURORA_DRY_RUN_MAX_ORDER_NOTIONAL_USD": "100",
        }, clear=True):
            result = self.engine.evaluate_and_create_shadow_order(
                base_intent(quantity=2, limit_price=100.0),
                fresh_market_data(),
            )

        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["reason"], "ORDER_NOTIONAL_LIMIT_EXCEEDED")

    def test_spread_limit_is_enforced(self):
        with patch.dict(os.environ, {
            "AURORA_RUN_MODE": "DRY_RUN",
            "AURORA_DRY_RUN_MAX_SPREAD_BPS": "50",
        }, clear=True):
            result = self.engine.evaluate_and_create_shadow_order(
                base_intent(),
                fresh_market_data(bid=99.0, ask=101.0),
            )

        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["reason"], "SPREAD_LIMIT_EXCEEDED")

    def test_daily_gross_notional_limit_is_enforced(self):
        with patch.dict(os.environ, {
            "AURORA_RUN_MODE": "DRY_RUN",
            "AURORA_DRY_RUN_MAX_ORDER_NOTIONAL_USD": "100",
            "AURORA_DRY_RUN_MAX_DAILY_GROSS_NOTIONAL_USD": "150",
        }, clear=True):
            first = self.engine.evaluate_and_create_shadow_order(
                base_intent(
                    idempotency_key="signal-a",
                    limit_price=75.0,
                ),
                fresh_market_data(last_price=75.0, bid=74.95, ask=75.05),
            )
            second = self.engine.evaluate_and_create_shadow_order(
                base_intent(
                    idempotency_key="signal-b",
                    limit_price=80.0,
                ),
                fresh_market_data(last_price=80.0, bid=79.95, ask=80.05),
            )

        self.assertEqual(first["status"], "SHADOW_ACCEPTED")
        self.assertEqual(second["status"], "BLOCKED")
        self.assertEqual(
            second["reason"],
            "DAILY_GROSS_NOTIONAL_LIMIT_EXCEEDED",
        )

    def test_broker_submission_method_is_hard_blocked(self):
        with self.assertRaisesRegex(
            RuntimeError,
            "DRY_RUN_BROKER_SUBMISSION_HARD_BLOCKED",
        ):
            self.engine.submit_to_broker({"symbol": "NVDA"})


if __name__ == "__main__":
    unittest.main()
