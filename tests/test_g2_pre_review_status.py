"""G8.5 tests for the fail-closed G2 pre-review status gate."""

import unittest

from scripts.g2_pre_review_status import (
    evaluate_pre_review_status,
)
from scripts.gateway_review_package import (
    RUNTIME_BOUND_PACKAGE_SCHEMA_VERSION,
    RUNTIME_BOUND_PACKAGE_TYPE,
)


RUN_ID = "11111111-1111-4111-8111-111111111111"
INSTANCE_ID = "1234567890123456789"


def g2_proof(run_id=RUN_ID):
    return {
        "evidence_run_id": run_id,
    }


def handoff():
    return {
        "status": "READY_FOR_INDEPENDENT_REVIEW",
    }


def package(run_id=RUN_ID):
    return {
        "status": "READY_FOR_INDEPENDENT_REVIEW_PACKAGE",
        "package_type": RUNTIME_BOUND_PACKAGE_TYPE,
        "package_schema_version": RUNTIME_BOUND_PACKAGE_SCHEMA_VERSION,
        "ready_for_independent_review": True,
        "attestation_verified": False,
        "gateway_read_only_configuration_independently_attested": False,
        "failure_reasons": [],
        "g2_diagnostic_proof_sha256": "a" * 64,
        "handoff_request_sha256": "b" * 64,
        "g2_diagnostic_summary": {
            "evidence_run_id": run_id,
            "gcp_instance_id": INSTANCE_ID,
            "g0_runtime_proof_sha256": "c" * 64,
        },
        "broker_submission_allowed": False,
        "paper_order_submission_allowed": False,
        "live_execution_allowed": False,
        "automatic_promotion_allowed": False,
        "real_money_trading_allowed": False,
    }


class G2PreReviewStatusTests(unittest.TestCase):
    def evaluate(
        self,
        expected_run_id=RUN_ID,
        proof=None,
        package_result=None,
    ):
        return evaluate_pre_review_status(
            expected_run_id,
            proof if proof is not None else g2_proof(),
            handoff(),
            review_package_result=(
                package_result
                if package_result is not None
                else package()
            ),
        )

    def test_ready_package_advances_only_to_human_independent_review(self):
        result = self.evaluate()

        self.assertEqual(
            result["status"],
            "READY_FOR_INDEPENDENT_REVIEW",
        )
        self.assertEqual(
            result["next_action"],
            "COMPLETE_INDEPENDENT_GATEWAY_READ_ONLY_REVIEW",
        )
        self.assertTrue(result["human_action_required"])
        self.assertEqual(result["evidence_run_id"], RUN_ID)
        self.assertEqual(result["gcp_instance_id"], INSTANCE_ID)
        self.assertEqual(
            result["review_package_type"],
            RUNTIME_BOUND_PACKAGE_TYPE,
        )
        for name in (
            "broker_submission_allowed",
            "paper_order_submission_allowed",
            "live_execution_allowed",
            "automatic_promotion_allowed",
            "real_money_trading_allowed",
        ):
            self.assertIs(result[name], False)

    def test_invalid_or_mismatched_run_id_fails_closed(self):
        invalid = self.evaluate(
            expected_run_id="not-a-uuid",
        )
        self.assertEqual(invalid["status"], "BLOCKED")
        self.assertIn(
            "EXPECTED_EVIDENCE_RUN_ID_INVALID",
            invalid["failure_reasons"],
        )

        mismatch = self.evaluate(
            proof=g2_proof(
                "22222222-2222-4222-8222-222222222222"
            ),
        )
        self.assertEqual(mismatch["status"], "BLOCKED")
        self.assertIn(
            "G2_DIAGNOSTIC_EVIDENCE_RUN_MISMATCH",
            mismatch["failure_reasons"],
        )

    def test_package_run_id_mismatch_fails_closed(self):
        value = package(
            "22222222-2222-4222-8222-222222222222"
        )
        result = self.evaluate(
            package_result=value,
        )

        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn(
            "REVIEW_PACKAGE_NOT_READY",
            result["failure_reasons"],
        )

    def test_any_execution_permission_regression_fails_closed(self):
        for name in (
            "broker_submission_allowed",
            "paper_order_submission_allowed",
            "live_execution_allowed",
            "automatic_promotion_allowed",
            "real_money_trading_allowed",
        ):
            with self.subTest(name=name):
                value = package()
                value[name] = True
                result = self.evaluate(
                    package_result=value,
                )
                self.assertEqual(result["status"], "BLOCKED")
                self.assertIn(
                    "EXECUTION_PERMISSION_INVARIANT_FAILED",
                    result["failure_reasons"],
                )

    def test_missing_binding_digest_or_instance_fails_closed(self):
        cases = []

        missing_g2_digest = package()
        missing_g2_digest["g2_diagnostic_proof_sha256"] = None
        cases.append(missing_g2_digest)

        missing_handoff_digest = package()
        missing_handoff_digest["handoff_request_sha256"] = None
        cases.append(missing_handoff_digest)

        missing_g0_digest = package()
        missing_g0_digest["g2_diagnostic_summary"][
            "g0_runtime_proof_sha256"
        ] = None
        cases.append(missing_g0_digest)

        invalid_instance = package()
        invalid_instance["g2_diagnostic_summary"][
            "gcp_instance_id"
        ] = "not-an-instance"
        cases.append(invalid_instance)

        for value in cases:
            with self.subTest(value=value):
                result = self.evaluate(
                    package_result=value,
                )
                self.assertEqual(result["status"], "BLOCKED")
                self.assertIn(
                    "PRE_REVIEW_BINDING_INVALID",
                    result["failure_reasons"],
                )

    def test_not_ready_package_exposes_only_sanitized_reason(self):
        value = package()
        value["status"] = "BLOCKED"
        value["ready_for_independent_review"] = False
        value["failure_reasons"] = [
            "G2_DIAGNOSTIC_NOT_FRESH"
        ]

        result = self.evaluate(
            package_result=value,
        )

        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(
            result["failure_reasons"],
            ["G2_DIAGNOSTIC_NOT_FRESH"],
        )
        self.assertNotIn("g2_diagnostic_summary", result)


if __name__ == "__main__":
    unittest.main()
