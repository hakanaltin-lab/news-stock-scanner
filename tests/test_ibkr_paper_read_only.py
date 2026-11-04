"""Offline safety tests for the IBKR Paper read-only milestone."""

import importlib.util
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

from engines import ibkr_gateway_connector as connector
from scripts import ibkr_paper_probe as paper_probe
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
            "client_id": 82,
            "client_id_valid": True,
        },
        "official_ibapi_available": True,
        "order_submission_hard_blocked": True,
        "broker_mutation_surface_hard_blocked": True,
        "open_order_observation_mode": "REQ_ALL_OPEN_ORDERS_NON_BINDING",
        "client_zero_binding_hard_blocked": True,
        "gateway_read_only_configuration_independently_attested": True,
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
        "open_orders": [],
        "requests_complete": {
            "managed_accounts": True,
            "account_summary": True,
            "positions": True,
            "open_orders": True,
        },
    }


class IBKRConnectorConfigurationTests(unittest.TestCase):
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
        self.assertTrue(snapshot["broker_mutation_surface_hard_blocked"])
        self.assertEqual(
            snapshot["open_order_observation_mode"],
            "REQ_ALL_OPEN_ORDERS_NON_BINDING",
        )

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

    def test_invalid_port_never_falls_back_to_paper_port(self):
        for value in ("not-a-port", "4002.0", "0", "65536"):
            with self.subTest(value=value), patch.dict(os.environ, {
                "AURORA_IBKR_ENABLED": "true",
                "AURORA_IBKR_MODE": "PAPER",
                "AURORA_IBKR_PORT": value,
            }, clear=True):
                config = connector.load_ibkr_config()
                snapshot = connector.get_ibkr_read_only_snapshot()

            self.assertFalse(config["port_valid"])
            self.assertEqual(snapshot["status"], "BLOCKED")
            self.assertEqual(snapshot["connection_status"], "NOT_ATTEMPTED")
            self.assertEqual(snapshot["reason"], "INVALID_IBKR_PORT")

    def test_invalid_client_id_blocks_before_network_access(self):
        for value in ("not-an-id", "-1", "0", "2147483648"):
            with self.subTest(value=value), patch.dict(os.environ, {
                "AURORA_IBKR_ENABLED": "true",
                "AURORA_IBKR_MODE": "PAPER",
                "AURORA_IBKR_HOST": "127.0.0.1",
                "AURORA_IBKR_PORT": "4002",
                "AURORA_IBKR_CLIENT_ID": value,
            }, clear=True):
                config = connector.load_ibkr_config()
                snapshot = connector.get_ibkr_read_only_snapshot()

            self.assertFalse(config["client_id_valid"])
            self.assertEqual(snapshot["status"], "BLOCKED")
            self.assertEqual(snapshot["connection_status"], "NOT_ATTEMPTED")
            self.assertEqual(snapshot["reason"], "INVALID_IBKR_CLIENT_ID")

    def test_invalid_timeout_blocks_before_network_access(self):
        for value in ("not-a-timeout", "nan", "inf", "-inf", "0", "31"):
            with self.subTest(value=value), patch.dict(os.environ, {
                "AURORA_IBKR_ENABLED": "true",
                "AURORA_IBKR_MODE": "PAPER",
                "AURORA_IBKR_HOST": "127.0.0.1",
                "AURORA_IBKR_PORT": "4002",
                "AURORA_IBKR_CLIENT_ID": "82",
                "AURORA_IBKR_TIMEOUT_SECONDS": value,
            }, clear=True):
                config = connector.load_ibkr_config()
                snapshot = connector.get_ibkr_read_only_snapshot()

            self.assertFalse(config["timeout_valid"])
            self.assertEqual(snapshot["status"], "BLOCKED")
            self.assertEqual(snapshot["connection_status"], "NOT_ATTEMPTED")
            self.assertEqual(snapshot["reason"], "INVALID_IBKR_TIMEOUT_SECONDS")

    def test_safe_float_rejects_non_finite_and_boolean_values(self):
        for value in (float("nan"), float("inf"), float("-inf"), True, False):
            with self.subTest(value=value):
                self.assertIsNone(connector.safe_float(value))

    def test_invalid_broker_numeric_callbacks_do_not_become_zero(self):
        fake_ibapi = types.ModuleType("ibapi")
        fake_client = types.ModuleType("ibapi.client")
        fake_wrapper = types.ModuleType("ibapi.wrapper")

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
            "ibkr_connector_numeric_fail_closed_test",
            module_path,
        )
        isolated = importlib.util.module_from_spec(specification)

        with patch.dict(sys.modules, {
            "ibapi": fake_ibapi,
            "ibapi.client": fake_client,
            "ibapi.wrapper": fake_wrapper,
        }):
            specification.loader.exec_module(isolated)

        application = isolated._IBKRSnapshotApp()

        class Contract:
            symbol = "NVDA"
            secType = "STK"
            currency = "USD"
            exchange = "SMART"
            conId = 4815747

        application.position(
            "DU-REDACTED",
            Contract(),
            float("nan"),
            float("inf"),
        )
        self.assertEqual(application.positions[0]["con_id"], 4815747)
        sanitized_position = isolated._sanitize_positions(
            application.positions
        )[0]
        self.assertEqual(sanitized_position["con_id"], 4815747)
        self.assertIsNone(application.positions[0]["position"])
        self.assertIsNone(application.positions[0]["average_cost"])

        application.orderStatus(
            1,
            "Submitted",
            float("nan"),
            float("inf"),
            "not-a-number",
            10,
            0,
            0.0,
            82,
            "",
            0.0,
        )
        self.assertIsNone(application.order_status_rows[0]["filled"])
        self.assertIsNone(application.order_status_rows[0]["remaining"])
        self.assertIsNone(application.order_status_rows[0]["average_fill_price"])

        class Execution:
            execId = "E1"
            side = "BOT"
            shares = float("nan")
            price = float("inf")
            time = "20261102 09:00:00"

        application.execDetails(1, Contract(), Execution())
        self.assertIsNone(application.execution_rows[0]["shares"])
        self.assertIsNone(application.execution_rows[0]["price"])

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

    def test_broker_mutation_surface_is_hard_blocked_even_with_ibapi_available(self):
        fake_ibapi = types.ModuleType("ibapi")
        fake_client = types.ModuleType("ibapi.client")
        fake_wrapper = types.ModuleType("ibapi.wrapper")

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
            "ibkr_connector_mutation_block_test",
            module_path,
        )
        isolated = importlib.util.module_from_spec(specification)

        with patch.dict(sys.modules, {
            "ibapi": fake_ibapi,
            "ibapi.client": fake_client,
            "ibapi.wrapper": fake_wrapper,
        }):
            specification.loader.exec_module(isolated)

        application = isolated._IBKRSnapshotApp()

        for method_name in isolated.BROKER_MUTATION_METHODS_HARD_BLOCKED:
            with self.subTest(method_name=method_name):
                self.assertIn(
                    method_name,
                    isolated._IBKRSnapshotApp.__dict__,
                )
                with self.assertRaisesRegex(RuntimeError, "hard-blocked"):
                    getattr(application, method_name)()

    def test_open_order_probe_uses_nonbinding_request(self):
        source = (
            REPOSITORY_ROOT
            / "engines/ibkr_gateway_connector.py"
        ).read_text(encoding="utf-8")

        self.assertIn("app.reqAllOpenOrders()", source)
        self.assertNotIn("app.reqOpenOrders()", source)


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

    def test_duplicate_open_order_identifier_blocks_readiness(self):
        snapshot = ready_snapshot()
        snapshot["open_orders"] = [
            {
                "account": "IBKR-TESTACCOUNT",
                "order_id": 10,
                "symbol": "NVDA",
            },
            {
                "account": "IBKR-TESTACCOUNT",
                "order_id": 10,
                "symbol": "AMD",
            },
        ]

        readiness = evaluate_ibkr_paper_readiness(snapshot, [])

        self.assertEqual(readiness["readiness"], "NOT_READY")
        self.assertIn(
            "open_order_identifiers_unique",
            {
                item["check"] for item in readiness["checks"]
                if item["required"] and not item["passed"]
            },
        )
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
            "security_type": "STK",
            "currency": "USD",
            "con_id": 4815747,
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

    def test_gateway_read_only_requires_independent_attestation(self):
        snapshot = ready_snapshot()
        snapshot["gateway_read_only_configuration_independently_attested"] = False

        readiness = evaluate_ibkr_paper_readiness(snapshot, [])

        self.assertEqual(readiness["readiness"], "NOT_READY")
        self.assertTrue(readiness["diagnostic_read_only_ready"])
        self.assertEqual(
            readiness["next_milestone"],
            "INDEPENDENT_GATEWAY_READ_ONLY_ATTESTATION",
        )
        self.assertFalse(
            readiness[
                "gateway_read_only_configuration_independently_attested"
            ]
        )

    def test_connector_cannot_self_attest_gateway_read_only(self):
        with patch.dict(os.environ, {
            "AURORA_IBKR_ENABLED": "false",
            "AURORA_IBKR_MODE": "PAPER",
            "AURORA_IBKR_GATEWAY_READ_ONLY_ATTESTED": "true",
        }, clear=True):
            snapshot = connector.get_ibkr_read_only_snapshot()

        self.assertIs(
            snapshot[
                "gateway_read_only_configuration_independently_attested"
            ],
            False,
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
            self.assertEqual(
                summary["status"],
                "BLOCKED_BEFORE_BROKER_CONNECTION",
            )
            self.assertFalse(output.exists())
            self.assertFalse(summary["paper_order_submission_allowed"])
            self.assertFalse(summary["live_execution_allowed"])




class IBKRRuntimeEvidenceFileTests(unittest.TestCase):
    def test_atomic_runtime_writer_creates_owner_only_regular_file(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "latest.json"
            payload = {
                "status": "SAFE",
                "paper_order_submission_allowed": False,
                "live_execution_allowed": False,
            }

            paper_probe.write_runtime_evidence_atomic(
                target,
                payload,
            )

            metadata = target.stat()
            self.assertTrue(
                stat.S_ISREG(metadata.st_mode)
            )
            self.assertEqual(
                stat.S_IMODE(metadata.st_mode),
                paper_probe.RUNTIME_EVIDENCE_MODE,
            )
            self.assertEqual(metadata.st_nlink, 1)
            self.assertEqual(
                json.loads(target.read_text(encoding="utf-8")),
                payload,
            )
            leftovers = [
                item.name
                for item in target.parent.iterdir()
                if item.name.startswith(".aurora-g2-")
            ]
            self.assertEqual(leftovers, [])

    def test_atomic_runtime_writer_refuses_existing_symlink_target(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            victim = root / "victim.json"
            victim.write_text(
                '{"unchanged":true}',
                encoding="utf-8",
            )
            target = root / "latest.json"
            target.symlink_to(victim)

            with self.assertRaisesRegex(
                RuntimeError,
                "target type invalid",
            ):
                paper_probe.write_runtime_evidence_atomic(
                    target,
                    {"safe": True},
                )

            self.assertEqual(
                victim.read_text(encoding="utf-8"),
                '{"unchanged":true}',
            )

    def test_atomic_runtime_writer_refuses_directory_target(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "latest.json"
            target.mkdir()

            with self.assertRaisesRegex(
                RuntimeError,
                "target type invalid",
            ):
                paper_probe.write_runtime_evidence_atomic(
                    target,
                    {"safe": True},
                )


class IBKRRuntimeProvenanceTests(unittest.TestCase):
    INSTANCE_ID = "1234567890123456789"

    def identity(self, instance_id=None):
        return {
            "status": "VERIFIED",
            "verified": True,
            "project_id": paper_probe.EXPECTED_PROJECT_ID,
            "instance_name": paper_probe.EXPECTED_INSTANCE_NAME,
            "zone": paper_probe.EXPECTED_ZONE,
            "instance_id": instance_id or self.INSTANCE_ID,
            "failure_reasons": [],
        }

    def g0_proof(self, instance_id=None):
        return {
            "engine": "AURORA V8.9.20 G0-G1 Runtime Proof",
            "status": "G0_G1_VERIFIED",
            "failure_reasons": [],
            "project_id": paper_probe.EXPECTED_PROJECT_ID,
            "vm_name": paper_probe.EXPECTED_INSTANCE_NAME,
            "zone": paper_probe.EXPECTED_ZONE,
            "gce_instance_id": instance_id or self.INSTANCE_ID,
            "checks": {
                name: True
                for name in paper_probe._REQUIRED_G0_CHECKS
            },
            "broker_submission_allowed": False,
            "paper_order_submission_allowed": False,
            "live_execution_allowed": False,
            "automatic_promotion_allowed": False,
        }

    def test_runtime_provenance_binds_verified_gce_identity_and_g0_digest(self):
        g0 = self.g0_proof()
        result = paper_probe.build_runtime_provenance(
            self.identity(),
            g0,
        )

        self.assertTrue(result["verified"])
        self.assertEqual(result["failure_reasons"], [])
        self.assertEqual(
            result["runtime_cloud_identity"]["instance_id"],
            self.INSTANCE_ID,
        )
        self.assertEqual(
            result["g0_runtime_proof_sha256"],
            paper_probe._canonical_sha256(g0),
        )
        self.assertFalse(result["paper_order_submission_allowed"])
        self.assertFalse(result["live_execution_allowed"])

    def test_runtime_provenance_rejects_cross_vm_g0_proof(self):
        result = paper_probe.build_runtime_provenance(
            self.identity(),
            self.g0_proof("9876543210987654321"),
        )

        self.assertFalse(result["verified"])
        self.assertIn(
            "G0_RUNTIME_PROOF_UNVERIFIED",
            result["failure_reasons"],
        )
        self.assertIsNone(result["g0_runtime_proof_sha256"])

    def test_runtime_provenance_rejects_unverified_metadata_identity(self):
        identity = self.identity()
        identity["status"] = "BLOCKED"
        identity["verified"] = False
        identity["failure_reasons"] = [
            "GCE_METADATA_IDENTITY_UNAVAILABLE"
        ]

        result = paper_probe.build_runtime_provenance(
            identity,
            self.g0_proof(),
        )

        self.assertFalse(result["verified"])
        self.assertIn(
            "GCE_RUNTIME_IDENTITY_UNVERIFIED",
            result["failure_reasons"],
        )
        self.assertIsNone(result["runtime_cloud_identity"])
        self.assertIsNone(result["g0_runtime_proof_sha256"])

    def test_runtime_provenance_rejects_g0_permission_regression(self):
        g0 = self.g0_proof()
        g0["paper_order_submission_allowed"] = True

        result = paper_probe.build_runtime_provenance(
            self.identity(),
            g0,
        )

        self.assertFalse(result["verified"])
        self.assertIn(
            "G0_RUNTIME_PROOF_UNVERIFIED",
            result["failure_reasons"],
        )
        self.assertFalse(result["paper_order_submission_allowed"])


if __name__ == "__main__":
    unittest.main()
