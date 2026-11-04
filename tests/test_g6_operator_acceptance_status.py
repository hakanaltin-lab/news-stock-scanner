"""G6 operator acceptance status is sanitized and non-executable."""
import unittest
from scripts.g6_operator_acceptance_status import build_g6_operator_acceptance_status

FLAGS = (
    "broker_submission_allowed",
    "paper_order_submission_allowed",
    "live_execution_allowed",
    "automatic_promotion_allowed",
    "real_money_trading_allowed",
)

IDENTITY = {
    "status": "VERIFIED",
    "verified": True,
    "failure_reasons": [],
    **{flag: False for flag in FLAGS},
}

def review(**overrides):
    base = {
        "status": "BLOCKED",
        "workflow_stage": "REVIEW_PACKAGE",
        "next_action": "RUN_FRESH_G2_DIAGNOSTIC_PRE_REVIEW",
        "signed_attestation_verified": False,
        **{flag: False for flag in FLAGS},
    }
    base.update(overrides)
    return base


class G6OperatorAcceptanceStatusTests(unittest.TestCase):
    def test_pre_review_diagnostic_is_safe_read_only_next_step(self):
        result = build_g6_operator_acceptance_status(IDENTITY, review())
        self.assertEqual(result["status"], "READY_FOR_SAFE_BROKER_READ")
        self.assertEqual(result["stage"], "PRE_REVIEW_DIAGNOSTIC")
        self.assertTrue(result["ready_for_broker_read"])
        self.assertTrue(all(result[flag] is False for flag in FLAGS))

    def test_waiting_for_human_review_never_allows_broker_read(self):
        result = build_g6_operator_acceptance_status(
            IDENTITY,
            review(
                status="WAITING_FOR_INDEPENDENT_REVIEW",
                workflow_stage="INDEPENDENT_REVIEW",
                next_action="COMPLETE_INDEPENDENT_REVIEW_AND_INSTALL_SIGNED_ATTESTATION",
            ),
        )
        self.assertEqual(result["status"], "WAITING_FOR_HUMAN_REVIEW")
        self.assertFalse(result["ready_for_broker_read"])

    def test_post_review_probe_is_safe_read_only_next_step(self):
        result = build_g6_operator_acceptance_status(
            IDENTITY,
            review(
                status="VERIFIED_FOR_G2_READ_ONLY_PROBE",
                workflow_stage="SIGNED_ATTESTATION_VERIFIED",
                next_action="RUN_G2_PAPER_READ_ONLY_PROBE",
                signed_attestation_verified=True,
            ),
        )
        self.assertEqual(result["stage"], "POST_REVIEW_PROBE")
        self.assertTrue(result["ready_for_broker_read"])

    def test_identity_permission_drift_blocks(self):
        unsafe_identity = dict(IDENTITY)
        unsafe_identity["paper_order_submission_allowed"] = True
        result = build_g6_operator_acceptance_status(unsafe_identity, review())
        self.assertEqual(result["status"], "BLOCKED")
        self.assertFalse(result["ready_for_broker_read"])

    def test_identity_or_permission_drift_blocks(self):
        result = build_g6_operator_acceptance_status(
            {"status": "BLOCKED", "verified": False, "failure_reasons": ["x"]},
            review(),
        )
        self.assertEqual(result["status"], "BLOCKED")
        self.assertFalse(result["ready_for_broker_read"])

        unsafe = review()
        unsafe["live_execution_allowed"] = True
        result = build_g6_operator_acceptance_status(IDENTITY, unsafe)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertFalse(result["ready_for_broker_read"])


if __name__ == "__main__":
    unittest.main()
