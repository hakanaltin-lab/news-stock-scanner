"""G7.12 tests for fail-closed independent-review workflow status."""

import inspect
import unittest
from unittest.mock import patch

import scripts.gateway_review_workflow_status as status


def safe_flags():
    return {
        "broker_submission_allowed": False,
        "paper_order_submission_allowed": False,
        "live_execution_allowed": False,
        "automatic_promotion_allowed": False,
        "real_money_trading_allowed": False,
    }


def identity(verified=True):
    return {
        **safe_flags(),
        "status": "VERIFIED" if verified else "BLOCKED",
        "verified": verified,
        "failure_reasons": [] if verified else ["BLOCKED"],
    }


def handoff(ready=True):
    return {
        **safe_flags(),
        "status": (
            "READY_FOR_INDEPENDENT_REVIEW"
            if ready
            else "BLOCKED"
        ),
        "ready_for_independent_review": ready,
        "attestation_verified": False,
        "gateway_read_only_configuration_independently_attested": False,
        "failure_reasons": [] if ready else ["BLOCKED"],
    }


def package(ready=True):
    return {
        **safe_flags(),
        "package_type": (
            status.RUNTIME_BOUND_PACKAGE_TYPE
            if ready
            else status.RUNTIME_BOUND_PACKAGE_TYPE
        ),
        "package_schema_version": status.RUNTIME_BOUND_PACKAGE_SCHEMA_VERSION,
        "status": (
            "READY_FOR_INDEPENDENT_REVIEW_PACKAGE"
            if ready
            else "BLOCKED"
        ),
        "ready_for_independent_review": ready,
        "attestation_verified": False,
        "gateway_read_only_configuration_independently_attested": False,
        "failure_reasons": [] if ready else ["BLOCKED"],
        "g2_diagnostic_proof_sha256": (
            "a" * 64
            if ready
            else None
        ),
        "g2_diagnostic_summary": (
            {"diagnostic_read_only_ready": True}
            if ready
            else None
        ),
    }


def attestation(verified=False):
    return {
        **safe_flags(),
        "status": "VERIFIED" if verified else "BLOCKED",
        "verified": verified,
        "gateway_read_only_configuration_independently_attested": verified,
        "failure_reasons": [] if verified else ["BLOCKED"],
    }


class GatewayReviewWorkflowStatusTests(unittest.TestCase):
    def evaluate(
        self,
        identity_value=None,
        handoff_value=None,
        package_value=None,
        attestation_value=None,
    ):
        return status.evaluate_gateway_review_workflow(
            identity_value if identity_value is not None else identity(),
            handoff_value if handoff_value is not None else handoff(),
            package_value if package_value is not None else package(),
            (
                attestation_value
                if attestation_value is not None
                else attestation()
            ),
        )

    def test_waiting_for_independent_review_is_non_authorizing(self):
        result = self.evaluate()

        self.assertEqual(
            result["status"],
            "WAITING_FOR_INDEPENDENT_REVIEW",
        )
        self.assertEqual(
            result["next_action"],
            "COMPLETE_INDEPENDENT_REVIEW_AND_INSTALL_SIGNED_ATTESTATION",
        )
        self.assertTrue(result["human_action_required"])
        self.assertTrue(result["review_package_ready"])
        self.assertFalse(result["signed_attestation_verified"])
        for name in status._PERMISSION_FLAGS:
            self.assertIs(result[name], False)

    def test_verified_attestation_advances_only_to_g2_read_only_probe(self):
        result = self.evaluate(
            attestation_value=attestation(True)
        )

        self.assertEqual(
            result["status"],
            "VERIFIED_FOR_G2_READ_ONLY_PROBE",
        )
        self.assertEqual(
            result["next_action"],
            "RUN_G2_PAPER_READ_ONLY_PROBE",
        )
        self.assertFalse(result["human_action_required"])
        self.assertTrue(result["signed_attestation_verified"])
        for name in status._PERMISSION_FLAGS:
            self.assertIs(result[name], False)

    def test_signed_attestation_does_not_expire_with_pre_review_g2_window(self):
        result = self.evaluate(
            package_value=package(False),
            attestation_value=attestation(True),
        )

        self.assertEqual(
            result["status"],
            "VERIFIED_FOR_G2_READ_ONLY_PROBE",
        )
        self.assertEqual(
            result["workflow_stage"],
            "SIGNED_ATTESTATION_VERIFIED",
        )
        self.assertFalse(result["review_package_ready"])
        self.assertTrue(result["signed_attestation_verified"])
        for name in status._PERMISSION_FLAGS:
            self.assertIs(result[name], False)

    def test_each_earlier_stage_maps_to_one_safe_next_action(self):
        cases = (
            (
                {"identity_value": identity(False)},
                "RUNTIME_IDENTITY",
                "FIX_APPROVED_GCE_RUNTIME_IDENTITY",
            ),
            (
                {"handoff_value": handoff(False)},
                "TRUST_AND_HANDOFF",
                "INSTALL_OR_REPAIR_ROOT_POLICY_PUBLIC_KEY_AND_G0_PROOF",
            ),
            (
                {"package_value": package(False)},
                "REVIEW_PACKAGE",
                "RUN_FRESH_G2_DIAGNOSTIC_PRE_REVIEW",
            ),
        )

        for overrides, stage, action in cases:
            with self.subTest(stage=stage):
                result = self.evaluate(**overrides)
                self.assertEqual(result["status"], "BLOCKED")
                self.assertEqual(result["workflow_stage"], stage)
                self.assertEqual(result["next_action"], action)
                self.assertTrue(result["human_action_required"])
                for name in status._PERMISSION_FLAGS:
                    self.assertIs(result[name], False)

    def test_any_execution_permission_true_forces_safety_block(self):
        for component in ("identity", "handoff", "package", "attestation"):
            with self.subTest(component=component):
                values = {
                    "identity_value": identity(),
                    "handoff_value": handoff(),
                    "package_value": package(),
                    "attestation_value": attestation(),
                }
                key = component + "_value"
                values[key]["paper_order_submission_allowed"] = True

                result = self.evaluate(**values)

                self.assertEqual(result["status"], "BLOCKED")
                self.assertEqual(
                    result["workflow_stage"],
                    "SAFETY_INVARIANT",
                )
                self.assertEqual(
                    result["next_action"],
                    "STOP_AND_REPAIR_PERMISSION_INVARIANT",
                )
                self.assertIn(
                    "EXECUTION_PERMISSION_INVARIANT_FAILED",
                    result["failure_reasons"],
                )

    def test_attestation_cannot_inject_execution_permission(self):
        injected = attestation(True)
        injected["paper_order_submission_allowed"] = True

        result = self.evaluate(
            attestation_value=injected
        )

        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(
            result["workflow_stage"],
            "SAFETY_INVARIANT",
        )
        self.assertIn(
            "EXECUTION_PERMISSION_INVARIANT_FAILED",
            result["failure_reasons"],
        )

    def test_missing_permission_flag_is_not_treated_as_safe(self):
        unsafe = identity()
        unsafe.pop("paper_order_submission_allowed")

        result = self.evaluate(
            identity_value=unsafe
        )

        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(
            result["workflow_stage"],
            "SAFETY_INVARIANT",
        )
        self.assertIn(
            "EXECUTION_PERMISSION_INVARIANT_FAILED",
            result["failure_reasons"],
        )

    def test_attestation_missing_permission_flag_is_not_treated_as_safe(self):
        unsafe = attestation(True)
        unsafe.pop("paper_order_submission_allowed")

        result = self.evaluate(
            attestation_value=unsafe
        )

        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(
            result["workflow_stage"],
            "SAFETY_INVARIANT",
        )
        self.assertIn(
            "EXECUTION_PERMISSION_INVARIANT_FAILED",
            result["failure_reasons"],
        )

    def test_contradictory_ready_payload_with_failures_is_blocked(self):
        contradictory = handoff()
        contradictory["failure_reasons"] = ["unexpected"]

        result = self.evaluate(
            handoff_value=contradictory
        )

        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(
            result["workflow_stage"],
            "TRUST_AND_HANDOFF",
        )

    def test_invalid_input_fails_closed_without_leaking_component_details(self):
        result = status.evaluate_gateway_review_workflow(
            [],
            handoff(),
            package(),
            attestation(),
        )

        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(
            result["failure_reasons"],
            ["WORKFLOW_INPUT_INVALID"],
        )
        self.assertNotIn("handoff_request", result)
        self.assertNotIn("failure_detail", result)

    def test_cli_exit_zero_only_after_signed_attestation_verifies(self):
        waiting = self.evaluate()
        with patch.object(
            status,
            "build_installed_gateway_review_workflow_status",
            return_value=waiting,
        ), patch("builtins.print"):
            self.assertEqual(status.main(), 2)

        verified = self.evaluate(
            attestation_value=attestation(True)
        )
        with patch.object(
            status,
            "build_installed_gateway_review_workflow_status",
            return_value=verified,
        ), patch("builtins.print"):
            self.assertEqual(status.main(), 0)

    def test_source_has_no_write_sign_or_order_submission_path(self):
        source = inspect.getsource(status).lower()
        for token in (
            "write_text",
            "write_bytes",
            "os.replace",
            "chmod",
            "pkeyutl",
            "placeorder",
            "submit_order",
            "decision\": \"attested",
        ):
            self.assertNotIn(token, source)


if __name__ == "__main__":
    unittest.main()
