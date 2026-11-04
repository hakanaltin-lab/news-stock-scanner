"""Prevent connecting to IBKR before signed G6 Paper read-only acceptance."""
import contextlib
import io
import unittest
from unittest.mock import patch
from scripts import ibkr_paper_probe as probe

FLAGS = ("broker_submission_allowed", "paper_order_submission_allowed",
         "live_execution_allowed", "automatic_promotion_allowed",
         "real_money_trading_allowed")

def review():
    return {"status": "VERIFIED_FOR_G2_READ_ONLY_PROBE",
            "next_action": "RUN_G2_PAPER_READ_ONLY_PROBE",
            "failure_reasons": [], **{x: False for x in FLAGS}}

MODE = {"mode": "READ_ONLY", "mode_valid": True,
        "read_only": True, "paper_order_submission_requested": False,
        "live_execution_allowed": False}

class G6PreconnectionTests(unittest.TestCase):
    def test_valid_approval_allows_readonly_probe(self):
        self.assertTrue(probe._preconnection_gate(MODE, {"verified": True}, review()))

    def test_live_mode_permission_drift_blocks(self):
        mode = dict(MODE, live_execution_allowed=True)
        self.assertFalse(probe._preconnection_gate(mode, {"verified": True}, review()))

    def test_missing_unverified_or_permission_drift_blocks(self):
        self.assertFalse(probe._preconnection_gate(MODE, {"verified": False}, review()))
        self.assertFalse(probe._preconnection_gate(MODE, {"verified": True}, {}))
        for flag in FLAGS:
            for value in (True, None):
                with self.subTest(flag=flag, value=value):
                    bad = review()
                    bad[flag] = value
                    self.assertFalse(probe._preconnection_gate(MODE, {"verified": True}, bad))

    def test_main_never_calls_broker_when_review_missing(self):
        with (patch.object(probe, "load_run_mode", return_value=MODE),
              patch.object(probe, "read_gce_runtime_identity", return_value={}),
              patch.object(probe, "load_g0_runtime_proof", return_value={}),
              patch.object(probe, "build_runtime_provenance", return_value={"verified": True}),
              patch.object(probe, "build_installed_gateway_review_workflow_status",
                           return_value={"status": "REVIEW_REQUIRED"}),
              patch.object(probe, "get_ibkr_read_only_snapshot") as broker,
              patch.object(probe, "write_runtime_evidence_atomic") as writer,
              contextlib.redirect_stdout(io.StringIO()) as output):
            self.assertEqual(probe.main(), 2)
            broker.assert_not_called()
            writer.assert_not_called()
            self.assertIn("BLOCKED_BEFORE_BROKER_CONNECTION", output.getvalue())

if __name__ == "__main__":
    unittest.main()
