"""AURORA V8.9.7 IBKR market-data connector safety tests."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from engines import ibkr_market_data_connector as connector


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_RUN_ID = "11111111-1111-4111-8111-111111111111"


class IBKRMarketDataEvaluationTests(unittest.TestCase):
    def test_verified_realtime_quote_is_execution_eligible(self):
        result = connector.evaluate_ibkr_quote_snapshot({
            "symbol": "NVDA",
            "market_data_type": 1,
            "bid": 100.0,
            "ask": 100.1,
            "last_price": 100.05,
            "market_timestamp": "2026-10-28T11:59:59+00:00",
            "received_at": "2026-10-28T12:00:00+00:00",
        })

        self.assertTrue(result["execution_eligible"])
        self.assertEqual(result["source"], "IBKR_REALTIME")
        self.assertEqual(
            result["market_data_type_name"],
            "REALTIME",
        )

    def test_realtime_quote_without_broker_timestamp_is_blocked(self):
        result = connector.evaluate_ibkr_quote_snapshot({
            "symbol": "NVDA",
            "market_data_type": 1,
            "bid": 100.0,
            "ask": 100.1,
            "last_price": 100.05,
            "received_at": "2026-10-28T12:00:00+00:00",
        })

        self.assertFalse(result["execution_eligible"])
        self.assertFalse(result["broker_market_timestamp_verified"])
        self.assertIn(
            "BROKER_MARKET_TIMESTAMP_REQUIRED",
            result["failure_reasons"],
        )

    def test_broker_epoch_timestamp_is_normalized_to_utc(self):
        result = connector.evaluate_ibkr_quote_snapshot({
            "symbol": "NVDA",
            "market_data_type": 1,
            "bid": 100.0,
            "ask": 100.1,
            "last_price": 100.05,
            "market_timestamp": 1793188799,
            "received_at": "2026-10-28T12:00:00+00:00",
        })

        self.assertTrue(result["execution_eligible"])
        self.assertTrue(result["broker_market_timestamp_verified"])
        self.assertTrue(result["market_timestamp"].endswith("+00:00"))

    def test_delayed_quote_is_never_execution_eligible(self):
        result = connector.evaluate_ibkr_quote_snapshot({
            "symbol": "NVDA",
            "market_data_type": 3,
            "bid": 100.0,
            "ask": 100.1,
            "last_price": 100.05,
        })

        self.assertFalse(result["execution_eligible"])
        self.assertEqual(
            result["market_data_type_name"],
            "DELAYED",
        )
        self.assertIn(
            "REALTIME_MARKET_DATA_REQUIRED",
            result["failure_reasons"],
        )

    def test_frozen_quote_is_never_execution_eligible(self):
        result = connector.evaluate_ibkr_quote_snapshot({
            "symbol": "NVDA",
            "market_data_type": 2,
            "bid": 100.0,
            "ask": 100.1,
            "last_price": 100.05,
        })

        self.assertFalse(result["execution_eligible"])
        self.assertEqual(
            result["market_data_type_name"],
            "FROZEN",
        )

    def test_incomplete_realtime_quote_is_blocked(self):
        result = connector.evaluate_ibkr_quote_snapshot({
            "symbol": "NVDA",
            "market_data_type": 1,
            "bid": 100.0,
            "ask": None,
            "last_price": 100.05,
        })

        self.assertFalse(result["execution_eligible"])
        self.assertIn(
            "VALID_BID_ASK_REQUIRED",
            result["failure_reasons"],
        )

    def test_crossed_or_invalid_quote_is_blocked(self):
        result = connector.evaluate_ibkr_quote_snapshot({
            "symbol": "NVDA",
            "market_data_type": 1,
            "bid": 101.0,
            "ask": 100.0,
            "last_price": 100.5,
        })

        self.assertFalse(result["execution_eligible"])
        self.assertIn(
            "VALID_BID_ASK_REQUIRED",
            result["failure_reasons"],
        )


class IBKRMarketDataConfigTests(unittest.TestCase):
    def test_connector_disabled_by_default(self):
        with patch.dict(os.environ, {}, clear=True):
            config = connector.load_ibkr_market_data_config()

        self.assertFalse(config["enabled"])
        self.assertTrue(config["endpoint_safe"])
        self.assertFalse(config["live_execution_allowed"])
        self.assertFalse(
            config["paper_order_submission_allowed"]
        )

    def test_live_port_is_unsafe(self):
        with patch.dict(os.environ, {
            "AURORA_IBKR_MODE": "PAPER",
            "AURORA_IBKR_HOST": "127.0.0.1",
            "AURORA_IBKR_PORT": "4001",
        }, clear=True):
            config = connector.load_ibkr_market_data_config()

        self.assertFalse(config["endpoint_safe"])

    def test_non_loopback_host_is_unsafe(self):
        with patch.dict(os.environ, {
            "AURORA_IBKR_MODE": "PAPER",
            "AURORA_IBKR_HOST": "10.20.0.5",
            "AURORA_IBKR_PORT": "4002",
        }, clear=True):
            config = connector.load_ibkr_market_data_config()

        self.assertFalse(config["endpoint_safe"])

    def test_unsafe_endpoint_blocks_before_api_use(self):
        with patch.dict(os.environ, {
            "AURORA_IBKR_MARKET_DATA_ENABLED": "true",
            "AURORA_IBKR_MODE": "PAPER",
            "AURORA_IBKR_HOST": "127.0.0.1",
            "AURORA_IBKR_PORT": "4001",
        }, clear=True):
            result = connector.get_ibkr_realtime_quote(
                "NVDA"
            )

        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(
            result["connection_status"],
            "NOT_ATTEMPTED",
        )
        self.assertFalse(
            result["config"]["endpoint_safe"]
        )

    def test_missing_symbol_fails_closed(self):
        with patch.dict(os.environ, {
            "AURORA_IBKR_MARKET_DATA_ENABLED": "true",
        }, clear=True):
            result = connector.get_ibkr_realtime_quote("")

        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["reason"], "SYMBOL_REQUIRED")


class IBKRMarketDataStaticSafetyTests(unittest.TestCase):
    def test_connector_contains_no_order_submission_path(self):
        source = (
            Path(__file__).resolve().parents[1]
            / "engines"
            / "ibkr_market_data_connector.py"
        ).read_text(encoding="utf-8")

        forbidden_tokens = [
            "placeOrder",
            "reqIds(",
            "submit_order",
            "Order()",
            "LIVE_EXECUTION_ALLOWED = True",
            "PAPER_ORDER_SUBMISSION_ALLOWED = True",
        ]

        for token in forbidden_tokens:
            self.assertNotIn(token, source)

        self.assertIn("reqTickByTickData", source)
        self.assertIn("tickByTickAllLast", source)

    def test_probe_preserves_wrapper_evidence_run_id(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "g3-proof.json"
            environment = os.environ.copy()
            environment.update({
                "AURORA_IBKR_MARKET_DATA_ENABLED": "false",
                "AURORA_IBKR_MODE": "PAPER",
                "AURORA_IBKR_MARKET_DATA_PROBE_OUTPUT": str(output),
                "AURORA_EVIDENCE_RUN_ID": EVIDENCE_RUN_ID,
            })
            completed = subprocess.run(
                [
                    sys.executable,
                    str(
                        REPOSITORY_ROOT
                        / "scripts"
                        / "ibkr_market_data_probe.py"
                    ),
                    "NVDA",
                ],
                cwd=directory,
                env=environment,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 2, completed.stderr)
            proof = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(proof["evidence_run_id"], EVIDENCE_RUN_ID)
            self.assertFalse(proof["broker_submission_allowed"])


if __name__ == "__main__":
    unittest.main()
