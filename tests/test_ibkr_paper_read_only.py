"""Offline safety tests for the IBKR Paper read-only milestone."""

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

from engines import ibkr_gateway_connector as connector
from engines.ibkr_paper_readiness_engine import evaluate_ibkr_paper_readiness


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_RUN_ID = "11111111-1111-4111-8111-111111111111"


def ready_snapshot():
    return {
        "status": "CONNECTED",
        "config": {
            "mode": "PAPER",
            "mode_valid": True,
            "read_only": True,
            "endpoint_safe": True,
        },
        "official_ibapi_available": True,
        "order_submission_hard_blocked": True,
        "live_trading_allowed": False,
        "account_count": 1,
        "accounts": ["IBKR-TESTACCOUNT"],
        "paper_account_guard": {
            "allowlist_configured": True,
            "managed_account_received": True,
            "account_count": 1,
            "all_accounts_allowlisted": True,
            "paper_account_verified": True,
            "verified_account_fingerprints": ["IBKR-TESTACCOUNT"],
            "reason": "PAPER_ACCOUNT_VERIFIED",
        },
        "account_summary_account_fingerprints": ["IBKR-TESTACCOUNT"],
        "account_summary": {
            "NetLiquidation": {"value": 100000.0, "currency": "USD"},
            "TotalCashValue": {"value": 50000.0, "currency": "USD"},
            "AvailableFunds": {"value": 45000.0, "currency": "USD"},
            "BuyingPower": {"value": 180000.0, "currency": "USD"},
        },
        "positions": [],
        "requests_complete": {
            "managed_accounts": True,
            "account_summary": True,
            "positions": True,
            "open_orders": True,
        },
    }


class IBKRConnectorConfigurationTests(unittest.TestCase):
    def test_nonfinite_gateway_timeout_is_safely_defaulted(self):
        for value in ("nan", "inf", "-inf"):
            with self.subTest(value=value), patch.dict(os.environ, {
                "AURORA_IBKR_TIMEOUT_SECONDS": value,
            }, clear=True):
                config = connector.load_ibkr_config()
                self.assertEqual(config["timeout_seconds"], 8.0)

    def test_disabled_connector_never_attempts_a_connection(self):
        with patch.dict(os.environ, {
            "AURORA_IBKR_ENABLED": "false",
            "AURORA_IBKR_MODE": "PAPER",
        }, clear=True):
            snapshot = connector.get_ibkr_read_only_snapshot()

        self.assertEqual(snapshot["status"], "DISABLED")
        self.assertEqual(snapshot["connection_status"], "NOT_ATTEMPTED")
        self.assertFalse(snapshot["live_trading_allowed"])
        self.assertTrue(snapshot["order_submission_hard_blocked"])

    def test_live_mode_is_blocked_before_api_or_network_access(self):
        with patch.dict(os.environ, {
            "AURORA_IBKR_ENABLED": "true",
            "AURORA_IBKR_MODE": "LIVE",
        }, clear=True):
            snapshot = connector.get_ibkr_read_only_snapshot()

        self.assertEqual(snapshot["status"], "BLOCKED")
        self.assertEqual(snapshot["connection_status"], "NOT_ATTEMPTED")
        self.assertEqual(snapshot["config"]["mode"], "LIVE")

    def test_invalid_mode_fails_closed_instead_of_becoming_paper(self):
        with patch.dict(os.environ, {
            "AURORA_IBKR_ENABLED": "true",
            "AURORA_IBKR_MODE": "PAPRE",
        }, clear=True):
            config = connector.load_ibkr_config()
            snapshot = connector.get_ibkr_read_only_snapshot()

        self.assertEqual(config["mode"], "INVALID")
        self.assertFalse(config["mode_valid"])
        self.assertEqual(snapshot["status"], "BLOCKED")
        self.assertEqual(snapshot["connection_status"], "NOT_ATTEMPTED")

    def test_non_loopback_host_is_blocked_before_network_access(self):
        with patch.dict(os.environ, {
            "AURORA_IBKR_ENABLED": "true",
            "AURORA_IBKR_MODE": "PAPER",
            "AURORA_IBKR_HOST": "10.20.0.5",
            "AURORA_IBKR_PORT": "4002",
        }, clear=True):
            snapshot = connector.get_ibkr_read_only_snapshot()

        self.assertEqual(snapshot["status"], "BLOCKED")
        self.assertEqual(snapshot["connection_status"], "NOT_ATTEMPTED")
        self.assertFalse(snapshot["config"]["endpoint_safe"])

    def test_live_gateway_port_is_blocked_before_network_access(self):
        with patch.dict(os.environ, {
            "AURORA_IBKR_ENABLED": "true",
            "AURORA_IBKR_MODE": "PAPER",
            "AURORA_IBKR_HOST": "127.0.0.1",
            "AURORA_IBKR_PORT": "4001",
        }, clear=True):
            snapshot = connector.get_ibkr_read_only_snapshot()

        self.assertEqual(snapshot["status"], "BLOCKED")
        self.assertEqual(snapshot["connection_status"], "NOT_ATTEMPTED")
        self.assertFalse(snapshot["config"]["endpoint_safe"])

    def test_account_identifiers_are_masked_in_errors(self):
        account = "DU1234567"
        sanitized = connector._sanitize_errors([{
            "request_id": -1,
            "code": 999,
            "message": "Account DU1234567 is unavailable",
        }], [account])

        self.assertNotIn(account, sanitized[0]["message"])
        self.assertIn(connector.mask_account(account), sanitized[0]["message"])

    def test_account_summary_account_ids_are_fingerprinted(self):
        rows = [
            {
                "account": "DU1234567",
                "tag": "NetLiquidation",
                "value": "100000",
                "currency": "USD",
            },
        ]

        fingerprints = connector._account_summary_fingerprints(rows)

        self.assertEqual(
            fingerprints,
            [connector.mask_account("DU1234567")],
        )
        self.assertNotIn("DU1234567", fingerprints)

    def test_place_order_is_hard_blocked_even_with_ibapi_available(self):
        fake_ibapi = types.ModuleType("ibapi")
        fake_client = types.ModuleType("ibapi.client")
        fake_wrapper = types.ModuleType("ibapi.wrapper")
        fake_execution = types.ModuleType("ibapi.execution")
        fake_execution.ExecutionFilter = type("ExecutionFilter", (), {})

        class FakeClient:
            def __init__(self, wrapper):
                self.wrapper = wrapper

        class FakeWrapper:
            def __init__(self):
                pass

        fake_client.EClient = FakeClient
        fake_wrapper.EWrapper = FakeWrapper

        module_path = REPOSITORY_ROOT / "engines/ibkr_gateway_connector.py"
        specification = importlib.util.spec_from_file_location(
            "ibkr_connector_order_block_test",
            module_path,
        )
        isolated = importlib.util.module_from_spec(specification)

        with patch.dict(sys.modules, {
            "ibapi": fake_ibapi,
            "ibapi.client": fake_client,
            "ibapi.wrapper": fake_wrapper,
            "ibapi.execution": fake_execution,
        }):
            specification.loader.exec_module(isolated)

        application = isolated._IBKRSnapshotApp()

        with self.assertRaisesRegex(RuntimeError, "hard-blocked"):
            application.placeOrder(1, object(), object())


    def test_open_order_callback_captures_broker_identity(self):
        fake_ibapi = types.ModuleType("ibapi")
        fake_client = types.ModuleType("ibapi.client")
        fake_wrapper = types.ModuleType("ibapi.wrapper")
        fake_execution = types.ModuleType("ibapi.execution")
        class FakeClient:
            def __init__(self, wrapper):
                self.wrapper = wrapper
        class FakeWrapper:
            def __init__(self):
                pass
        fake_client.EClient = FakeClient
        fake_wrapper.EWrapper = FakeWrapper
        fake_execution.ExecutionFilter = type("ExecutionFilter", (), {})
        specification = importlib.util.spec_from_file_location(
            "ibkr_connector_open_order_identity_test",
            REPOSITORY_ROOT / "engines/ibkr_gateway_connector.py",
        )
        isolated = importlib.util.module_from_spec(specification)
        with patch.dict(sys.modules, {
            "ibapi": fake_ibapi,
            "ibapi.client": fake_client,
            "ibapi.wrapper": fake_wrapper,
            "ibapi.execution": fake_execution,
        }):
            specification.loader.exec_module(isolated)
        app = isolated._IBKRSnapshotApp()
        order = types.SimpleNamespace(
            permId=123, clientId=82, account="DU1234567",
            action="BUY", orderType="LMT", totalQuantity=1, lmtPrice=10,
        )
        contract = types.SimpleNamespace(symbol="AAPL", secType="STK")
        state = types.SimpleNamespace(status="Submitted")
        app.openOrder(1, contract, order, state)
        row = app.open_orders[0]
        self.assertEqual(row["perm_id"], 123)
        self.assertEqual(row["client_id"], 82)
        self.assertEqual(row["order_id"], 1)
        self.assertEqual(row["account"], isolated.mask_account("DU1234567"))
        self.assertNotEqual(row["account"], "DU1234567")

    def test_unrelated_execution_request_is_ignored(self):
        fake_ibapi = types.ModuleType("ibapi")
        fake_client = types.ModuleType("ibapi.client")
        fake_wrapper = types.ModuleType("ibapi.wrapper")
        fake_execution = types.ModuleType("ibapi.execution")
        class FakeClient:
            def __init__(self, wrapper):
                self.wrapper = wrapper
        class FakeWrapper:
            def __init__(self):
                pass
        fake_client.EClient = FakeClient
        fake_wrapper.EWrapper = FakeWrapper
        fake_execution.ExecutionFilter = type("ExecutionFilter", (), {})
        specification = importlib.util.spec_from_file_location(
            "ibkr_connector_req_id_test",
            REPOSITORY_ROOT / "engines/ibkr_gateway_connector.py",
        )
        isolated = importlib.util.module_from_spec(specification)
        with patch.dict(sys.modules, {
            "ibapi": fake_ibapi,
            "ibapi.client": fake_client,
            "ibapi.wrapper": fake_wrapper,
            "ibapi.execution": fake_execution,
        }):
            specification.loader.exec_module(isolated)
        app = isolated._IBKRSnapshotApp()
        app.execDetails(9999, object(), object())
        self.assertEqual(app.execution_rows, [])
        self.assertFalse(app.executions_event.is_set())
        app.execDetailsEnd(9999)
        self.assertFalse(app.executions_event.is_set())


class IBKRReadinessTests(unittest.TestCase):
    def test_complete_snapshot_reaches_read_only_only(self):
        readiness = evaluate_ibkr_paper_readiness(
            ready_snapshot(),
            [],
        )

        self.assertEqual(readiness["readiness"], "READY_FOR_PAPER_READ_ONLY")
        self.assertEqual(readiness["required_failure_count"], 0)
        self.assertFalse(readiness["paper_order_submission_allowed"])
        self.assertFalse(readiness["live_execution_allowed"])

    def test_missing_managed_account_completion_is_not_ready(self):
        snapshot = ready_snapshot()
        snapshot["requests_complete"]["managed_accounts"] = False

        readiness = evaluate_ibkr_paper_readiness(snapshot, [])

        self.assertEqual(readiness["readiness"], "NOT_READY")
        failed = {
            item["check"]
            for item in readiness["checks"]
            if item["required"] and not item["passed"]
        }
        self.assertIn("managed_accounts_snapshot_complete", failed)

    def test_snapshot_account_identity_mismatch_is_not_ready(self):
        snapshot = ready_snapshot()
        snapshot["accounts"] = ["IBKR-OTHERACCOUNT"]
        readiness = evaluate_ibkr_paper_readiness(snapshot, [])
        self.assertEqual(readiness["readiness"], "NOT_READY")
        self.assertIn(
            "managed_account_identity_consistent",
            {
                item["check"] for item in readiness["checks"]
                if item["required"] and not item["passed"]
            },
        )

    def test_guard_account_count_mismatch_is_not_ready(self):
        snapshot = ready_snapshot()
        snapshot["paper_account_guard"]["account_count"] = 2
        readiness = evaluate_ibkr_paper_readiness(snapshot, [])
        self.assertEqual(readiness["readiness"], "NOT_READY")
        self.assertIn(
            "managed_account_identity_consistent",
            {
                item["check"] for item in readiness["checks"]
                if item["required"] and not item["passed"]
            },
        )

    def test_multiple_managed_accounts_are_not_ready(self):
        snapshot = ready_snapshot()
        snapshot["account_count"] = 2
        snapshot["paper_account_guard"]["account_count"] = 2
        snapshot["paper_account_guard"]["verified_account_fingerprints"] = [
            "IBKR-TESTACCOUNT",
            "IBKR-SECONDACCOUNT",
        ]
        snapshot["account_summary_account_fingerprints"] = [
            "IBKR-SECONDACCOUNT",
            "IBKR-TESTACCOUNT",
        ]

        readiness = evaluate_ibkr_paper_readiness(snapshot, [])

        self.assertEqual(readiness["readiness"], "NOT_READY")
        failed = {
            item["check"]
            for item in readiness["checks"]
            if item["required"] and not item["passed"]
        }
        self.assertIn("single_managed_account_for_readiness", failed)

    def test_foreign_open_order_blocks_readiness(self):
        snapshot = ready_snapshot()
        snapshot["open_orders"] = [{
            "account": "IBKR-OTHERACCOUNT",
            "order_id": 10,
            "symbol": "NVDA",
        }]
        readiness = evaluate_ibkr_paper_readiness(snapshot, [])
        self.assertEqual(readiness["readiness"], "NOT_READY")
        self.assertIn(
            "open_order_accounts_match_verified_paper_accounts",
            {
                item["check"] for item in readiness["checks"]
                if item["required"] and not item["passed"]
            },
        )

    def test_verified_paper_open_order_is_accepted(self):
        snapshot = ready_snapshot()
        snapshot["open_orders"] = [{
            "account": "IBKR-TESTACCOUNT",
            "order_id": 10,
            "symbol": "NVDA",
        }]
        readiness = evaluate_ibkr_paper_readiness(snapshot, [])
        self.assertEqual(readiness["readiness"], "READY_FOR_PAPER_READ_ONLY")
        self.assertFalse(readiness["paper_order_submission_allowed"])

    def test_open_order_missing_account_blocks_readiness(self):
        snapshot = ready_snapshot()
        snapshot["open_orders"] = [{"order_id": 10, "symbol": "NVDA"}]
        readiness = evaluate_ibkr_paper_readiness(snapshot, [])
        self.assertEqual(readiness["readiness"], "NOT_READY")

    def test_foreign_paper_position_blocks_readiness(self):
        snapshot = ready_snapshot()
        snapshot["positions"] = [{
            "account": "IBKR-OTHERACCOUNT",
            "symbol": "NVDA",
            "position": 1,
        }]
        readiness = evaluate_ibkr_paper_readiness(snapshot, [])
        self.assertEqual(readiness["readiness"], "NOT_READY")
        self.assertIn(
            "position_accounts_match_verified_paper_accounts",
            {
                item["check"] for item in readiness["checks"]
                if item["required"] and not item["passed"]
            },
        )

    def test_verified_paper_position_is_accepted(self):
        snapshot = ready_snapshot()
        snapshot["positions"] = [{
            "account": "IBKR-TESTACCOUNT",
            "symbol": "NVDA",
            "position": 1,
        }]
        readiness = evaluate_ibkr_paper_readiness(snapshot, [])
        self.assertEqual(readiness["readiness"], "READY_FOR_PAPER_READ_ONLY")
        self.assertFalse(readiness["paper_order_submission_allowed"])

    def test_position_missing_account_blocks_readiness(self):
        snapshot = ready_snapshot()
        snapshot["positions"] = [{"symbol": "NVDA", "position": 1}]
        readiness = evaluate_ibkr_paper_readiness(snapshot, [])
        self.assertEqual(readiness["readiness"], "NOT_READY")

    def test_incomplete_account_summary_blocks_read_only_readiness(self):
        snapshot = ready_snapshot()
        snapshot["requests_complete"]["account_summary"] = False
        readiness = evaluate_ibkr_paper_readiness(snapshot, [])
        self.assertEqual(readiness["readiness"], "NOT_READY")
        self.assertFalse(readiness["paper_order_submission_allowed"])
        self.assertFalse(readiness["live_execution_allowed"])
        failed = {
            check["check"]
            for check in readiness["checks"]
            if check["required"] and not check["passed"]
        }
        self.assertIn("account_summary_snapshot_complete", failed)

    def test_mismatched_account_summary_account_is_not_ready(self):
        snapshot = ready_snapshot()
        snapshot["account_summary_account_fingerprints"] = ["IBKR-OTHERACCOUNT"]

        readiness = evaluate_ibkr_paper_readiness(snapshot, [])

        self.assertEqual(readiness["readiness"], "NOT_READY")
        self.assertFalse(readiness["paper_order_submission_allowed"])
        self.assertFalse(readiness["live_execution_allowed"])
        failed = {
            item["check"]
            for item in readiness["checks"]
            if item["required"] and not item["passed"]
        }
        self.assertIn(
            "account_summary_accounts_match_managed_accounts",
            failed,
        )

    def test_missing_order_block_evidence_is_not_ready(self):
        snapshot = ready_snapshot()
        snapshot["order_submission_hard_blocked"] = False

        readiness = evaluate_ibkr_paper_readiness(snapshot, [])

        self.assertEqual(readiness["readiness"], "NOT_READY")
        self.assertGreaterEqual(readiness["required_failure_count"], 1)


class IBKRProbeEntrypointTests(unittest.TestCase):
    def test_direct_script_entrypoint_runs_from_an_unrelated_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "ibkr-proof.json"
            environment = os.environ.copy()
            environment.pop("PYTHONPATH", None)
            environment.update({
                "AURORA_IBKR_ENABLED": "false",
                "AURORA_IBKR_MODE": "PAPER",
                "AURORA_IBKR_PROBE_OUTPUT": str(output),
                "AURORA_EVIDENCE_RUN_ID": EVIDENCE_RUN_ID,
            })

            completed = subprocess.run(
                [
                    sys.executable,
                    str(REPOSITORY_ROOT / "scripts/ibkr_paper_probe.py"),
                ],
                cwd=directory,
                env=environment,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 2, completed.stderr)
            summary = json.loads(completed.stdout)
            proof = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(summary["run_mode"], "SAFE_OFF")
            self.assertEqual(summary["snapshot_status"], "DISABLED")
            self.assertEqual(proof["run_mode"]["mode"], "SAFE_OFF")
            self.assertEqual(proof["evidence_run_id"], EVIDENCE_RUN_ID)
            self.assertEqual(proof["readiness"]["readiness"], "DISABLED")
            self.assertFalse(proof["readiness"]["live_execution_allowed"])


if __name__ == "__main__":
    unittest.main()
