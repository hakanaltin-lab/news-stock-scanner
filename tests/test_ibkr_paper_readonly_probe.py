"""Offline tests for the operator-only Paper probe: no network or orders."""
import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

from scripts import ibkr_paper_readonly_probe as probe


class PaperProbeTests(unittest.TestCase):
    def test_direct_script_from_unrelated_directory_is_safely_disabled(self):
        script = Path(probe.__file__).resolve()
        with tempfile.TemporaryDirectory() as directory:
            env = os.environ.copy()
            env.pop("PYTHONPATH", None)
            env["AURORA_IBKR_ENABLED"] = "false"
            result = subprocess.run(
                [sys.executable, str(script)],
                cwd=directory, env=env, capture_output=True, text=True,
                timeout=15, check=False,
            )
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(json.loads(result.stdout)["status"], "BLOCKED")

    def test_disabled_probe_never_calls_connector(self):
        output = io.StringIO()
        with patch.dict(os.environ, {}, clear=True), patch.object(
            probe, "get_ibkr_read_only_snapshot"
        ) as connector, contextlib.redirect_stdout(output):
            result = probe.main()
        self.assertEqual(result, 2)
        connector.assert_not_called()
        self.assertEqual(json.loads(output.getvalue())["status"], "BLOCKED")

    def test_live_port_never_calls_connector(self):
        env = {"AURORA_IBKR_ENABLED": "true", "AURORA_IBKR_MODE": "PAPER",
               "AURORA_IBKR_HOST": "127.0.0.1", "AURORA_IBKR_PORT": "4001"}
        with patch.dict(os.environ, env, clear=True), patch.object(
            probe, "get_ibkr_read_only_snapshot"
        ) as connector, contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(probe.main(), 2)
        connector.assert_not_called()

    def test_redacted_output_and_complete_paper_readiness(self):
        env = {"AURORA_IBKR_ENABLED": "true", "AURORA_IBKR_MODE": "PAPER",
               "AURORA_IBKR_HOST": "127.0.0.1", "AURORA_IBKR_PORT": "4002"}
        snapshot = {"status": "CONNECTED", "connection_status": "CONNECTED",
                    "config": {"endpoint_safe": True},
                    "order_submission_hard_blocked": True,
                    "paper_account_guard": {"paper_account_verified": True},
                    "accounts": ["DU1234567"], "errors": [{"message": "SECRET"}],
                    "requests_complete": dict.fromkeys(
                        ("managed_accounts", "account_summary", "positions",
                         "open_orders", "executions"), True)}
        output = io.StringIO()
        with patch.dict(os.environ, env, clear=True), patch.object(
            probe, "get_ibkr_read_only_snapshot", return_value=snapshot
        ), contextlib.redirect_stdout(output):
            self.assertEqual(probe.main(), 0)
        self.assertNotIn("DU1234567", output.getvalue())
        self.assertNotIn("SECRET", output.getvalue())
        self.assertTrue(json.loads(output.getvalue())["hard_blocked"])

    def test_incomplete_execution_snapshot_is_not_ready(self):
        env = {"AURORA_IBKR_ENABLED": "true", "AURORA_IBKR_MODE": "PAPER",
               "AURORA_IBKR_HOST": "127.0.0.1", "AURORA_IBKR_PORT": "4002"}
        snapshot = {"status": "CONNECTED", "config": {"endpoint_safe": True},
                    "order_submission_hard_blocked": True,
                    "paper_account_guard": {"paper_account_verified": True},
                    "requests_complete": {"managed_accounts": True,
                                          "account_summary": True,
                                          "positions": True, "open_orders": True,
                                          "executions": False}}
        with patch.dict(os.environ, env, clear=True), patch.object(
            probe, "get_ibkr_read_only_snapshot", return_value=snapshot
        ), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(probe.main(), 1)


if __name__ == "__main__":
    unittest.main()
