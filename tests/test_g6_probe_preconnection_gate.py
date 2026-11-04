"""Prevent IBKR socket use before signed G6 Paper read-only acceptance."""
import contextlib
import io
import unittest
from unittest.mock import patch
from scripts import ibkr_paper_probe as probe

FLAGS = (
    "broker_submission_allowed",
    "paper_order_submission_allowed",
    "live_execution_allowed",
    "automatic_promotion_allowed",
    "real_money_trading_allowed",
)

MODE = {
    "mode": "READ_ONLY",
    "mode_valid": True,
    "read_only": True,
    "paper_order_submission_requested": False,
    "live_execution_allowed": False,
}


def post_review():
    return {
        "status": "VERIFIED_FOR_G2_READ_ONLY_PROBE",
        "workflow_stage": "SIGNED_ATTESTATION_VERIFIED",
        "next_action": "RUN_G2_PAPER_READ_ONLY_PROBE",
        "human_action_required": False,
        "runtime_identity_verified": True,
        "handoff_ready": True,
        "review_package_ready": False,
        "signed_attestation_verified": True,
        "failure_reasons": [],
        **{name: False for name in FLAGS},
    }


def pre_review():
    return {
        "status": "BLOCKED",
        "workflow_stage": "REVIEW_PACKAGE",
        "next_action": "RUN_FRESH_G2_DIAGNOSTIC_PRE_REVIEW",
        "human_action_required": True,
        "runtime_identity_verified": True,
        "handoff_ready": True,
        "review_package_ready": False,
        "signed_attestation_verified": False,
        "failure_reasons": ["G2_DIAGNOSTIC_REVIEW_PACKAGE_NOT_READY"],
        **{name: False for name in FLAGS},
    }


class G6ProbePreconnectionGateTests(unittest.TestCase):
    def test_signed_review_allows_post_review_probe(self):
        self.assertEqual(
            probe._preconnection_stage(
                MODE,
                {"verified": True},
                post_review(),
            ),
            "POST_REVIEW_PROBE",
        )

    def test_handoff_allows_only_pre_review_diagnostic(self):
        self.assertEqual(
            probe._preconnection_stage(
                MODE,
                {"verified": True},
                pre_review(),
            ),
            "PRE_REVIEW_DIAGNOSTIC",
        )

    def test_unverified_runtime_or_review_blocks(self):
        self.assertFalse(
            probe._preconnection_gate(
                MODE,
                {"verified": False},
                post_review(),
            )
        )
        self.assertFalse(
            probe._preconnection_gate(
                MODE,
                {"verified": True},
                {},
            )
        )

    def test_waiting_for_human_review_blocks_further_broker_reads(self):
        waiting = pre_review()
        waiting.update({
            "status": "WAITING_FOR_INDEPENDENT_REVIEW",
            "workflow_stage": "INDEPENDENT_REVIEW",
            "next_action": "COMPLETE_INDEPENDENT_REVIEW_AND_INSTALL_SIGNED_ATTESTATION",
            "review_package_ready": True,
            "failure_reasons": [],
        })
        self.assertIsNone(
            probe._preconnection_stage(
                MODE,
                {"verified": True},
                waiting,
            )
        )

    def test_each_execution_permission_must_be_explicit_false(self):
        for flag in FLAGS:
            for value in (True, None):
                with self.subTest(flag=flag, value=value):
                    bad = post_review()
                    bad[flag] = value
                    self.assertFalse(
                        probe._preconnection_gate(
                            MODE,
                            {"verified": True},
                            bad,
                        )
                    )

    def test_live_mode_drift_blocks(self):
        bad_mode = dict(MODE)
        bad_mode["live_execution_allowed"] = True
        self.assertFalse(
            probe._preconnection_gate(
                bad_mode,
                {"verified": True},
                post_review(),
            )
        )

    def test_main_never_connects_or_writes_when_review_missing(self):
        with (
            patch.object(probe, "load_run_mode", return_value=MODE),
            patch.object(probe, "read_gce_runtime_identity", return_value={}),
            patch.object(probe, "load_g0_runtime_proof", return_value={}),
            patch.object(
                probe,
                "build_runtime_provenance",
                return_value={"verified": True},
            ),
            patch.object(
                probe,
                "build_installed_gateway_review_workflow_status",
                return_value={"status": "REVIEW_REQUIRED"},
            ),
            patch.object(probe, "get_ibkr_read_only_snapshot") as broker,
            patch.object(probe, "write_runtime_evidence_atomic") as writer,
            contextlib.redirect_stdout(io.StringIO()) as output,
        ):
            self.assertEqual(probe.main(), 2)
            broker.assert_not_called()
            writer.assert_not_called()
            self.assertIn(
                "BLOCKED_BEFORE_BROKER_CONNECTION",
                output.getvalue(),
            )


if __name__ == "__main__":
    unittest.main()
