"""Offline tests for the safe GCE identity bootstrap CLI."""

import inspect
import json
import subprocess
import sys
import unittest
from unittest.mock import patch

from scripts import gce_identity_bootstrap as bootstrap


def verified_identity():
    return {
        "engine": "AURORA G7.7 GCE Runtime Identity",
        "status": "VERIFIED",
        "verified": True,
        "project_id": "project-ce9773ef-6814-469c-92b",
        "instance_name": "aurora-trading-vps",
        "zone": "europe-west3-a",
        "instance_id": "1234567890123456789",
        "failure_reasons": [],
    }


class SafeGCEIdentityBootstrapTests(unittest.TestCase):
    def test_verified_identity_is_sanitized_and_non_authorizing(self):
        with patch.object(
            bootstrap,
            "read_gce_runtime_identity",
            return_value=verified_identity(),
        ):
            result = bootstrap.build_bootstrap_identity()

        self.assertEqual(result["status"], "VERIFIED")
        self.assertEqual(result["instance_id"], "1234567890123456789")
        for key in (
            "policy_write_allowed",
            "attestation_write_allowed",
            "broker_submission_allowed",
            "paper_order_submission_allowed",
            "live_execution_allowed",
            "automatic_promotion_allowed",
            "real_money_trading_allowed",
        ):
            self.assertIs(result[key], False)

    def test_blocked_identity_discloses_no_partial_runtime_identity(self):
        blocked = verified_identity()
        blocked.update({
            "status": "BLOCKED",
            "verified": False,
            "failure_reasons": ["GCE_METADATA_IDENTITY_UNAVAILABLE"],
        })
        with patch.object(
            bootstrap,
            "read_gce_runtime_identity",
            return_value=blocked,
        ):
            result = bootstrap.build_bootstrap_identity()

        self.assertEqual(result["status"], "BLOCKED")
        for key in ("project_id", "instance_name", "zone", "instance_id"):
            self.assertIsNone(result[key])
        self.assertFalse(result["paper_order_submission_allowed"])

    def test_bootstrap_source_has_no_mutation_or_secret_metadata_path(self):
        source = inspect.getsource(bootstrap).lower()
        for token in (
            "service-accounts",
            "/token",
            "credential",
            "placeorder",
            "submit_order",
            "chmod",
            "write_text",
            "write_bytes",
        ):
            self.assertNotIn(token, source)

    def test_cli_fails_closed_outside_gce(self):
        completed = subprocess.run(
            [sys.executable, bootstrap.__file__],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertIn(completed.returncode, (0, 2))
        payload = json.loads(completed.stdout)
        self.assertFalse(payload["paper_order_submission_allowed"])
        self.assertFalse(payload["live_execution_allowed"])


if __name__ == "__main__":
    unittest.main()
