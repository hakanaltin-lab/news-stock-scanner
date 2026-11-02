"""AURORA V8.9.7 IBKR market-data connector safety tests."""

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import types
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
        self.assertTrue(config["mode_valid"])
        self.assertTrue(config["port_valid"])
        self.assertTrue(config["client_id_valid"])
        self.assertTrue(config["timeout_valid"])
        self.assertTrue(config["read_only"])

    def test_invalid_mode_blocks_before_network_access(self):
        with patch.dict(os.environ, {
            "AURORA_IBKR_MARKET_DATA_ENABLED": "true",
            "AURORA_IBKR_MODE": "PAPRE",
            "AURORA_IBKR_HOST": "127.0.0.1",
            "AURORA_IBKR_PORT": "4002",
        }, clear=True):
            config = connector.load_ibkr_market_data_config()
            result = connector.get_ibkr_realtime_quote("NVDA")

        self.assertEqual(config["mode"], "INVALID")
        self.assertFalse(config["mode_valid"])
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["connection_status"], "NOT_ATTEMPTED")
        self.assertEqual(result["reason"], "INVALID_IBKR_MODE")

    def test_invalid_port_blocks_without_safe_fallback(self):
        for value in ("not-a-port", "0", "65536"):
            with self.subTest(value=value), patch.dict(os.environ, {
                "AURORA_IBKR_MARKET_DATA_ENABLED": "true",
                "AURORA_IBKR_MODE": "PAPER",
                "AURORA_IBKR_HOST": "127.0.0.1",
                "AURORA_IBKR_PORT": value,
            }, clear=True):
                config = connector.load_ibkr_market_data_config()
                result = connector.get_ibkr_realtime_quote("NVDA")

            self.assertFalse(config["port_valid"])
            self.assertEqual(result["status"], "BLOCKED")
            self.assertEqual(result["connection_status"], "NOT_ATTEMPTED")
            self.assertEqual(result["reason"], "INVALID_IBKR_PORT")

    def test_invalid_or_zero_client_id_blocks_before_network_access(self):
        for value in ("not-an-id", "-1", "0", "2147483648"):
            with self.subTest(value=value), patch.dict(os.environ, {
                "AURORA_IBKR_MARKET_DATA_ENABLED": "true",
                "AURORA_IBKR_MODE": "PAPER",
                "AURORA_IBKR_HOST": "127.0.0.1",
                "AURORA_IBKR_PORT": "4002",
                "AURORA_IBKR_MARKET_DATA_CLIENT_ID": value,
            }, clear=True):
                config = connector.load_ibkr_market_data_config()
                result = connector.get_ibkr_realtime_quote("NVDA")

            self.assertFalse(config["client_id_valid"])
            self.assertEqual(result["status"], "BLOCKED")
            self.assertEqual(result["connection_status"], "NOT_ATTEMPTED")
            self.assertEqual(
                result["reason"],
                "INVALID_IBKR_MARKET_DATA_CLIENT_ID",
            )

    def test_invalid_timeout_blocks_without_safe_fallback(self):
        for value in ("not-a-timeout", "nan", "inf", "-inf", "0", "31"):
            with self.subTest(value=value), patch.dict(os.environ, {
                "AURORA_IBKR_MARKET_DATA_ENABLED": "true",
                "AURORA_IBKR_MODE": "PAPER",
                "AURORA_IBKR_HOST": "127.0.0.1",
                "AURORA_IBKR_PORT": "4002",
                "AURORA_IBKR_MARKET_DATA_CLIENT_ID": "83",
                "AURORA_IBKR_MARKET_DATA_TIMEOUT_SECONDS": value,
            }, clear=True):
                config = connector.load_ibkr_market_data_config()
                result = connector.get_ibkr_realtime_quote("NVDA")

            self.assertFalse(config["timeout_valid"])
            self.assertEqual(result["status"], "BLOCKED")
            self.assertEqual(result["connection_status"], "NOT_ATTEMPTED")
            self.assertEqual(
                result["reason"],
                "INVALID_IBKR_MARKET_DATA_TIMEOUT",
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

    def test_broker_mutation_surface_is_hard_blocked_with_ibapi_available(self):
        fake_ibapi = types.ModuleType("ibapi")
        fake_client = types.ModuleType("ibapi.client")
        fake_contract = types.ModuleType("ibapi.contract")
        fake_wrapper = types.ModuleType("ibapi.wrapper")

        class FakeClient:
            def __init__(self, wrapper):
                self.wrapper = wrapper

        class FakeContract:
            pass

        class FakeWrapper:
            def __init__(self):
                pass

        fake_client.EClient = FakeClient
        fake_contract.Contract = FakeContract
        fake_wrapper.EWrapper = FakeWrapper

        module_path = (
            REPOSITORY_ROOT
            / "engines"
            / "ibkr_market_data_connector.py"
        )
        specification = importlib.util.spec_from_file_location(
            "ibkr_market_data_mutation_block_test",
            module_path,
        )
        isolated = importlib.util.module_from_spec(specification)

        with patch.dict(sys.modules, {
            "ibapi": fake_ibapi,
            "ibapi.client": fake_client,
            "ibapi.contract": fake_contract,
            "ibapi.wrapper": fake_wrapper,
        }):
            specification.loader.exec_module(isolated)

        application = isolated._IBKRMarketDataApp()

        for method_name in isolated.BROKER_MUTATION_METHODS_HARD_BLOCKED:
            with self.subTest(method_name=method_name):
                self.assertIn(
                    method_name,
                    isolated._IBKRMarketDataApp.__dict__,
                )
                with self.assertRaisesRegex(
                    RuntimeError,
                    "hard-blocked",
                ):
                    getattr(application, method_name)()

    def test_disabled_snapshot_declares_mutation_hard_blocks(self):
        with patch.dict(os.environ, {
            "AURORA_IBKR_MARKET_DATA_ENABLED": "false",
            "AURORA_IBKR_MODE": "PAPER",
            "AURORA_IBKR_HOST": "127.0.0.1",
            "AURORA_IBKR_PORT": "4002",
            "AURORA_IBKR_MARKET_DATA_CLIENT_ID": "83",
        }, clear=True):
            result = connector.get_ibkr_realtime_quote("NVDA")

        self.assertEqual(result["status"], "DISABLED")
        self.assertTrue(
            result["broker_mutation_surface_hard_blocked"]
        )
        self.assertTrue(
            result["client_zero_binding_hard_blocked"]
        )
        self.assertEqual(
            set(result["blocked_broker_mutation_methods"]),
            set(connector.BROKER_MUTATION_METHODS_HARD_BLOCKED),
        )

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
