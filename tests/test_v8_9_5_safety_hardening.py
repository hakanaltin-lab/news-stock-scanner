"""Offline V8.9.5 safety-hardening regression tests."""

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from engines.aurora_run_mode_engine import (
    DRY_RUN,
    PAPER_ENABLED,
    READ_ONLY,
    SAFE_OFF,
    can_transition,
    load_run_mode,
    restart_state,
)
from engines.ibkr_account_guard import evaluate_paper_account_identity
from engines.market_data_quality_gate import evaluate_market_data_for_execution
from execution_engine.broker_connector import BrokerConnector as LegacyExecutionConnector
from engines.broker_connector import BrokerConnector as LegacyEngineConnector

from broker_engine.broker_execution_connector import (
    BrokerExecutionConnector as LegacyBrokerExecutionConnector,
)
from broker_engine.live_trading_bridge import LiveTradingBridge
from broker_engine.order_management_system import OrderManagementSystem
from deployment_engine.environment_manager import EnvironmentManager


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


class PaperAccountGuardTests(unittest.TestCase):
    def test_known_paper_account_passes_without_echoing_raw_account(self):
        raw_account = "DU1234567"
        with patch.dict(os.environ, {
            "AURORA_IBKR_PAPER_ACCOUNT_ALLOWLIST": raw_account,
        }, clear=True):
            result = evaluate_paper_account_identity([raw_account])

        self.assertTrue(result["paper_account_verified"])
        self.assertTrue(result["allowlist_configured"])
        self.assertNotIn(raw_account, json.dumps(result))

    def test_unknown_account_fails_closed(self):
        with patch.dict(os.environ, {
            "AURORA_IBKR_PAPER_ACCOUNT_ALLOWLIST": "DU7654321",
        }, clear=True):
            result = evaluate_paper_account_identity(["DU1234567"])

        self.assertFalse(result["paper_account_verified"])
        self.assertEqual(result["reason"], "PAPER_ACCOUNT_NOT_ALLOWLISTED")

    def test_missing_allowlist_fails_closed(self):
        with patch.dict(os.environ, {}, clear=True):
            result = evaluate_paper_account_identity(["DU1234567"])

        self.assertFalse(result["paper_account_verified"])
        self.assertEqual(result["reason"], "PAPER_ACCOUNT_ALLOWLIST_NOT_CONFIGURED")


class RunModeControllerTests(unittest.TestCase):
    def test_default_is_safe_off(self):
        with patch.dict(os.environ, {}, clear=True):
            state = load_run_mode()

        self.assertEqual(state["mode"], SAFE_OFF)
        self.assertFalse(state["live_execution_allowed"])
        self.assertFalse(state["paper_order_submission_requested"])

    def test_live_mode_string_cannot_enable_live(self):
        with patch.dict(os.environ, {
            "AURORA_RUN_MODE": "LIVE_ENABLED",
        }, clear=True):
            state = load_run_mode()

        self.assertEqual(state["mode"], SAFE_OFF)
        self.assertFalse(state["mode_valid"])
        self.assertFalse(state["live_execution_allowed"])

    def test_paper_enabled_requires_transition_path(self):
        self.assertTrue(can_transition(SAFE_OFF, READ_ONLY))
        self.assertTrue(can_transition(READ_ONLY, DRY_RUN))
        self.assertTrue(can_transition(DRY_RUN, PAPER_ENABLED))
        self.assertFalse(can_transition(SAFE_OFF, PAPER_ENABLED))

    def test_restart_always_returns_safe_off(self):
        state = restart_state()
        self.assertEqual(state["mode"], SAFE_OFF)
        self.assertFalse(state["paper_order_submission_requested"])
        self.assertFalse(state["live_execution_allowed"])


class MarketDataExecutionGateTests(unittest.TestCase):
    def test_yfinance_research_data_is_never_execution_eligible(self):
        now = datetime.now(timezone.utc)
        result = evaluate_market_data_for_execution({
            "source": "YFINANCE_15M",
            "market_timestamp": now.isoformat(),
            "last_price": 100.0,
            "data_points": 20,
            "data_quality": "AVAILABLE",
        }, now=now)

        self.assertFalse(result["execution_eligible"])
        self.assertIn("source_allowed", result["failure_reasons"])

    def test_fresh_ibkr_realtime_data_can_pass(self):
        now = datetime.now(timezone.utc)
        result = evaluate_market_data_for_execution({
            "source": "IBKR_REALTIME",
            "market_timestamp": now.isoformat(),
            "last_price": 100.0,
            "data_points": 1,
            "data_quality": "AVAILABLE",
        }, now=now)

        self.assertTrue(result["execution_eligible"])
        self.assertEqual(result["decision"], "PASS")

    def test_future_timestamp_is_blocked(self):
        now = datetime.now(timezone.utc)
        future = datetime.fromtimestamp(
            now.timestamp() + 30,
            tz=timezone.utc,
        )
        result = evaluate_market_data_for_execution({
            "source": "IBKR_REALTIME",
            "market_timestamp": future.isoformat(),
            "last_price": 100.0,
            "data_points": 1,
            "data_quality": "AVAILABLE",
        }, now=now)

        self.assertFalse(result["execution_eligible"])
        self.assertIn("clock_sane", result["failure_reasons"])

    def test_stale_ibkr_data_is_blocked(self):
        now = datetime.now(timezone.utc)
        stale = datetime.fromtimestamp(
            now.timestamp() - 60,
            tz=timezone.utc,
        )
        result = evaluate_market_data_for_execution({
            "source": "IBKR_REALTIME",
            "market_timestamp": stale.isoformat(),
            "last_price": 100.0,
            "data_points": 1,
            "data_quality": "AVAILABLE",
        }, now=now, max_age_seconds=10)

        self.assertFalse(result["execution_eligible"])
        self.assertIn("fresh", result["failure_reasons"])


class LegacyExecutionSurfaceTests(unittest.TestCase):
    def test_approved_legacy_broker_request_is_still_blocked(self):
        connector = LegacyBrokerExecutionConnector()
        order = connector.create_order_request(
            "NVDA",
            "BUY",
            1,
            "LIMIT",
            "APPROVED",
        )

        self.assertEqual(order["status"], "BLOCKED")
        self.assertFalse(order["live_execution_allowed"])
        self.assertFalse(order["paper_order_submission_allowed"])

    def test_live_trading_bridge_can_never_become_ready_or_executed(self):
        bridge = LiveTradingBridge()
        request = bridge.create_execution_request(
            "NVDA",
            "BUY",
            1,
            "APPROVED",
            "APPROVED",
        )

        self.assertEqual(request["status"], "BLOCKED")
        self.assertFalse(request["live_execution_allowed"])

        confirmed = bridge.confirm_execution(
            request["request_id"],
            {"status": "FILLED"},
        )
        self.assertEqual(confirmed["status"], "BLOCKED")
        self.assertNotEqual(confirmed["status"], "EXECUTED")

    def test_order_management_requires_dry_run_and_remains_shadow_only(self):
        manager = OrderManagementSystem()

        with patch.dict(os.environ, {
            "AURORA_RUN_MODE": "SAFE_OFF",
        }, clear=True):
            blocked = manager.create_trade_order(
                "NVDA", "BUY", 1, 100.0, 5.0, 10.0
            )

        self.assertEqual(blocked["status"], "BLOCKED")

        with patch.dict(os.environ, {
            "AURORA_RUN_MODE": "DRY_RUN",
        }, clear=True):
            shadow = manager.create_trade_order(
                "NVDA", "BUY", 1, 100.0, 5.0, 10.0
            )

        self.assertEqual(shadow["status"], "SHADOW_ONLY")
        self.assertFalse(shadow["live_execution_allowed"])
        self.assertFalse(shadow["paper_order_submission_allowed"])

    def test_environment_manager_rejects_live(self):
        manager = EnvironmentManager()

        blocked = manager.set_environment("LIVE")
        self.assertEqual(blocked["status"], "BLOCKED")
        self.assertEqual(manager.environment, "DEVELOPMENT")
        self.assertFalse(blocked["live_execution_allowed"])

        paper = manager.set_environment("PAPER")
        self.assertEqual(paper["status"], "UPDATED")
        self.assertEqual(manager.environment, "PAPER")
        self.assertFalse(paper["live_execution_allowed"])


class LegacyConnectorIsolationTests(unittest.TestCase):
    def test_legacy_execution_connector_never_reports_order_sent(self):
        connector = LegacyExecutionConnector()
        connection = connector.connect_broker("test-only", "PAPER")
        order = connector.submit_order("NVDA", 1, "LIMIT")

        self.assertEqual(connection["status"], "SIMULATION_ONLY")
        self.assertEqual(order["status"], "BLOCKED")
        self.assertNotIn("ORDER_SENT", json.dumps(order))

    def test_legacy_execution_connector_rejects_live(self):
        connector = LegacyExecutionConnector()
        connection = connector.connect_broker("test-only", "LIVE")

        self.assertEqual(connection["status"], "BLOCKED")
        self.assertFalse(connector.connected)

    def test_legacy_engine_connector_is_fail_closed(self):
        connector = LegacyEngineConnector("IBKR")
        connection = connector.connect()
        order = connector.submit_order({"symbol": "NVDA"})

        self.assertEqual(connection["status"], "BLOCKED")
        self.assertEqual(order["status"], "BLOCKED")

    def test_main_does_not_import_legacy_broker_connectors(self):
        source = (REPOSITORY_ROOT / "main.py").read_text(encoding="utf-8")
        self.assertNotIn("execution_engine.broker_connector", source)
        self.assertNotIn("from engines.broker_connector", source)


if __name__ == "__main__":
    unittest.main()
