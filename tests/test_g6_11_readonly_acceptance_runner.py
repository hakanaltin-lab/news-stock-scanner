"""Offline tests for the one-command G6.11 acceptance runner."""

import contextlib
import io
import json
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch

from scripts import run_g6_11_readonly_acceptance as runner


GIT_SHA = "a" * 40
RAW_ACCOUNT = "DU1234567"
HMAC_KEY = "ab" * 32


def valid_security():
    return {
        "status": "LOCAL_SECURITY_READY",
        "reason": "BROKER_LOGIN_AND_READ_ONLY_API_ACCEPTANCE_STILL_REQUIRED",
        "paper_order_submission_allowed": False,
        "live_trading_allowed": False,
        "release_approved": False,
    }


def valid_probe():
    return {
        "status": "CONNECTED",
        "connection_status": "CONNECTED",
        "paper_endpoint_safe": True,
        "hard_blocked": True,
        "live_trading_allowed": False,
        "paper_account_verified": True,
        "paper_account_evidence_token": "IBKR-EVID-ABCDEF1234567890",
        "snapshot_generated_at_utc": "2026-11-01T12:00:00+00:00",
        "requests_complete": {
            "managed_accounts": True,
            "account_summary": True,
            "positions": True,
            "open_orders": True,
            "executions": True,
        },
    }


class G611AcceptanceRunnerTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name)
        self.repo = root / "repo"
        self.repo.mkdir()
        self.evidence = root / "evidence"
        self.key_file = root / "config" / "evidence.key"
        self.allowlist_file = root / "config" / "allowlist"
        self.allowlist_file.parent.mkdir(parents=True)
        self.allowlist_file.write_text(RAW_ACCOUNT + "\n", encoding="utf-8")
        os.chmod(self.allowlist_file, 0o600)

    def tearDown(self):
        self.directory.cleanup()

    def run_with_probe(self, probe_payload=None, probe_exit=0):
        payload = valid_probe() if probe_payload is None else probe_payload

        def fake_probe():
            print(json.dumps(payload, sort_keys=True))
            return probe_exit

        with patch.object(runner, "_git_sha", return_value=GIT_SHA), patch.object(
            runner, "security_evaluate", return_value=valid_security()
        ), patch.object(runner.probe, "main", side_effect=fake_probe):
            result = runner.run(
                repo_path=self.repo,
                evidence_dir=self.evidence,
                key_file=self.key_file,
                allowlist_file=self.allowlist_file,
            )
        return result

    def test_success_writes_only_private_sanitized_evidence(self):
        result = self.run_with_probe()
        self.assertEqual(
            result["status"],
            "G6_11_READ_ONLY_EVIDENCE_CAPTURED",
        )
        self.assertFalse(result["paper_order_submission_allowed"])
        self.assertFalse(result["live_trading_allowed"])
        self.assertFalse(result["release_approved"])

        self.assertEqual(stat.S_IMODE(self.key_file.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(self.evidence.stat().st_mode), 0o700)

        written = list(self.evidence.glob("*.json"))
        self.assertGreaterEqual(len(written), 4)
        combined = ""
        for path in written:
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            combined += path.read_text(encoding="utf-8")

        key_value = self.key_file.read_text(encoding="utf-8").strip()
        self.assertNotIn(RAW_ACCOUNT, combined)
        self.assertNotIn(key_value, combined)
        self.assertNotIn("DU1234567", json.dumps(result))
        self.assertNotIn(key_value, json.dumps(result))

        bundle = Path(result["bundle_path"])
        payload = json.loads(bundle.read_text(encoding="utf-8"))
        self.assertEqual(
            payload["offline_validation"]["status"],
            "READ_ONLY_SNAPSHOT_VALIDATED",
        )
        self.assertFalse(payload["release_approved"])
        self.assertFalse(payload["evidence_authenticity_verified"])
        self.assertFalse(payload["broker_session_independently_verified"])

    def test_environment_is_restored_after_probe(self):
        original = os.environ.get("AURORA_IBKR_MODE")
        os.environ["AURORA_IBKR_MODE"] = "ORIGINAL"
        try:
            self.run_with_probe()
            self.assertEqual(os.environ.get("AURORA_IBKR_MODE"), "ORIGINAL")
            self.assertNotIn("AURORA_IBKR_EVIDENCE_HMAC_KEY", os.environ)
            self.assertNotIn("AURORA_IBKR_PAPER_ACCOUNT_ALLOWLIST", os.environ)
        finally:
            if original is None:
                os.environ.pop("AURORA_IBKR_MODE", None)
            else:
                os.environ["AURORA_IBKR_MODE"] = original

    def test_security_failure_stops_before_secret_or_broker_probe(self):
        blocked = {
            "status": "BLOCKED",
            "reason": "LOCAL_SECURITY_PREREQUISITES_INCOMPLETE",
            "paper_order_submission_allowed": False,
            "live_trading_allowed": False,
            "release_approved": False,
        }
        with patch.object(runner, "_git_sha", return_value=GIT_SHA), patch.object(
            runner, "security_evaluate", return_value=blocked
        ), patch.object(runner.probe, "main") as probe_main:
            result = runner.run(
                repo_path=self.repo,
                evidence_dir=self.evidence,
                key_file=self.key_file,
                allowlist_file=self.allowlist_file,
            )
        self.assertEqual(result["reason"], "LOCAL_SECURITY_PREFLIGHT_FAILED")
        probe_main.assert_not_called()
        self.assertFalse(self.key_file.exists())

    def test_missing_allowlist_blocks_before_probe(self):
        self.allowlist_file.unlink()
        with patch.object(runner, "_git_sha", return_value=GIT_SHA), patch.object(
            runner, "security_evaluate", return_value=valid_security()
        ), patch.object(runner.probe, "main") as probe_main:
            result = runner.run(
                repo_path=self.repo,
                evidence_dir=self.evidence,
                key_file=self.key_file,
                allowlist_file=self.allowlist_file,
            )
        self.assertEqual(
            result["reason"],
            "PAPER_ACCOUNT_ALLOWLIST_FILE_REQUIRED",
        )
        probe_main.assert_not_called()

    def test_insecure_allowlist_permissions_block(self):
        os.chmod(self.allowlist_file, 0o644)
        with patch.object(runner, "_git_sha", return_value=GIT_SHA), patch.object(
            runner, "security_evaluate", return_value=valid_security()
        ), patch.object(runner.probe, "main") as probe_main:
            result = runner.run(
                repo_path=self.repo,
                evidence_dir=self.evidence,
                key_file=self.key_file,
                allowlist_file=self.allowlist_file,
            )
        self.assertEqual(
            result["reason"],
            "PAPER_ACCOUNT_ALLOWLIST_PERMISSIONS_MUST_BE_0600",
        )
        probe_main.assert_not_called()

    def test_insecure_existing_hmac_key_permissions_block(self):
        self.key_file.parent.mkdir(parents=True, exist_ok=True)
        self.key_file.write_text(HMAC_KEY + "\n", encoding="utf-8")
        os.chmod(self.key_file, 0o644)
        with patch.object(runner, "_git_sha", return_value=GIT_SHA), patch.object(
            runner, "security_evaluate", return_value=valid_security()
        ), patch.object(runner.probe, "main") as probe_main:
            result = runner.run(
                repo_path=self.repo,
                evidence_dir=self.evidence,
                key_file=self.key_file,
                allowlist_file=self.allowlist_file,
            )
        self.assertEqual(
            result["reason"],
            "EVIDENCE_HMAC_KEY_PERMISSIONS_MUST_BE_0600",
        )
        probe_main.assert_not_called()

    def test_failed_probe_still_writes_sanitized_blocked_bundle(self):
        blocked_probe = {
            "status": "ERROR",
            "connection_status": "FAILED",
            "paper_endpoint_safe": True,
            "hard_blocked": True,
            "live_trading_allowed": False,
            "paper_account_verified": False,
            "paper_account_evidence_token": None,
            "snapshot_generated_at_utc": None,
            "requests_complete": {},
        }
        result = self.run_with_probe(blocked_probe, probe_exit=1)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["reason"], "READ_ONLY_ACCEPTANCE_NOT_PASSED")
        bundle = Path(result["bundle_path"])
        text = bundle.read_text(encoding="utf-8")
        self.assertNotIn(RAW_ACCOUNT, text)
        self.assertNotIn(
            self.key_file.read_text(encoding="utf-8").strip(),
            text,
        )

    def test_probe_exception_is_sanitized(self):
        with patch.object(runner, "_git_sha", return_value=GIT_SHA), patch.object(
            runner, "security_evaluate", return_value=valid_security()
        ), patch.object(
            runner.probe,
            "main",
            side_effect=RuntimeError("private-DU1234567-secret"),
        ):
            result = runner.run(
                repo_path=self.repo,
                evidence_dir=self.evidence,
                key_file=self.key_file,
                allowlist_file=self.allowlist_file,
            )
        self.assertEqual(result["status"], "BLOCKED")
        combined = "".join(
            path.read_text(encoding="utf-8")
            for path in self.evidence.glob("*.json")
        )
        self.assertNotIn("DU1234567", combined)
        self.assertNotIn("private-", combined)

    def test_invalid_probe_stdout_is_fail_closed(self):
        def fake_probe():
            print("not-json")
            return 0

        with patch.object(runner, "_git_sha", return_value=GIT_SHA), patch.object(
            runner, "security_evaluate", return_value=valid_security()
        ), patch.object(runner.probe, "main", side_effect=fake_probe):
            result = runner.run(
                repo_path=self.repo,
                evidence_dir=self.evidence,
                key_file=self.key_file,
                allowlist_file=self.allowlist_file,
            )
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["reason"], "READ_ONLY_ACCEPTANCE_NOT_PASSED")

    def test_missing_git_sha_blocks(self):
        with patch.object(runner, "_git_sha", return_value=None), patch.object(
            runner.probe, "main"
        ) as probe_main:
            result = runner.run(
                repo_path=self.repo,
                evidence_dir=self.evidence,
                key_file=self.key_file,
                allowlist_file=self.allowlist_file,
            )
        self.assertEqual(result["reason"], "REPOSITORY_GIT_SHA_UNAVAILABLE")
        probe_main.assert_not_called()


if __name__ == "__main__":
    unittest.main()
