"""Offline tests for local VPS security preflight."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import vps_local_security_preflight as preflight

class VpsLocalSecurityPreflightTests(unittest.TestCase):
    def test_local_only_services_can_be_ready_without_broker_auth(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            gw = Path(tmp) / "gw"
            repo.mkdir()
            gw.mkdir()
            (gw / "ibgateway").write_text("", encoding="utf-8")
            listeners = [
                "LISTEN 0 5 127.0.0.1:5902 0.0.0.0:*",
                "LISTEN 0 100 127.0.0.1:6080 0.0.0.0:*",
            ]
            with patch.object(preflight, "_git_sha", return_value="a"*40), patch.object(
                preflight, "_gateway_running", return_value=False
            ):
                result = preflight.evaluate(repo, gw, expected_sha="a"*40, listener_lines=listeners)
        self.assertEqual(result["status"], "LOCAL_SECURITY_READY")
        self.assertTrue(result["vnc_5902_local_only"])
        self.assertTrue(result["novnc_6080_local_only"])
        self.assertFalse(result["broker_auth_verified"])
        self.assertFalse(result["paper_order_submission_allowed"])
        self.assertFalse(result["live_trading_allowed"])
        self.assertFalse(result["release_approved"])

    def test_public_vnc_binding_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"; repo.mkdir()
            gw = Path(tmp) / "gw"; gw.mkdir(); (gw / "ibgateway").write_text("", encoding="utf-8")
            listeners = [
                "LISTEN 0 5 0.0.0.0:5902 0.0.0.0:*",
                "LISTEN 0 100 127.0.0.1:6080 0.0.0.0:*",
            ]
            with patch.object(preflight, "_git_sha", return_value="a"*40), patch.object(
                preflight, "_gateway_running", return_value=False
            ):
                result = preflight.evaluate(repo, gw, expected_sha="a"*40, listener_lines=listeners)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertFalse(result["vnc_5902_local_only"])

    def test_public_novnc_binding_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"; repo.mkdir()
            gw = Path(tmp) / "gw"; gw.mkdir(); (gw / "ibgateway").write_text("", encoding="utf-8")
            listeners = [
                "LISTEN 0 5 127.0.0.1:5902 0.0.0.0:*",
                "LISTEN 0 100 0.0.0.0:6080 0.0.0.0:*",
            ]
            with patch.object(preflight, "_git_sha", return_value="a"*40), patch.object(
                preflight, "_gateway_running", return_value=False
            ):
                result = preflight.evaluate(repo, gw, expected_sha="a"*40, listener_lines=listeners)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertFalse(result["novnc_6080_local_only"])

    def test_expected_sha_mismatch_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"; repo.mkdir()
            gw = Path(tmp) / "gw"; gw.mkdir(); (gw / "ibgateway").write_text("", encoding="utf-8")
            listeners = [
                "LISTEN 0 5 127.0.0.1:5902 0.0.0.0:*",
                "LISTEN 0 100 127.0.0.1:6080 0.0.0.0:*",
            ]
            with patch.object(preflight, "_git_sha", return_value="b"*40), patch.object(
                preflight, "_gateway_running", return_value=False
            ):
                result = preflight.evaluate(repo, gw, expected_sha="a"*40, listener_lines=listeners)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertFalse(result["repo_sha_matches_expected"])

    def test_missing_gateway_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"; repo.mkdir()
            gw = Path(tmp) / "missing"
            listeners = [
                "LISTEN 0 5 127.0.0.1:5902 0.0.0.0:*",
                "LISTEN 0 100 127.0.0.1:6080 0.0.0.0:*",
            ]
            with patch.object(preflight, "_git_sha", return_value="a"*40), patch.object(
                preflight, "_gateway_running", return_value=False
            ):
                result = preflight.evaluate(repo, gw, expected_sha="a"*40, listener_lines=listeners)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertFalse(result["ib_gateway_installed"])

if __name__ == "__main__":
    unittest.main()
