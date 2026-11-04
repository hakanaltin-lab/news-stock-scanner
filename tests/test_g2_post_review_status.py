"""G8.6 tests for strict post-attestation G2 run binding."""

import copy
import unittest

from engines.ibkr_paper_readiness_engine import (
    evaluate_ibkr_paper_readiness,
)
from scripts.g2_post_review_status import (
    evaluate_post_review_g2_status,
)


RUN_ID = "11111111-1111-4111-8111-111111111111"
ACCOUNT = "IBKR-TESTTOKEN"
INSTANCE_ID = "1234567890123456789"


def safe_permissions():
    return {
        "broker_submission_allowed": False,
        "paper_order_submission_allowed": False,
        "live_execution_allowed": False,
        "automatic_promotion_allowed": False,
        "real_money_trading_allowed": False,
    }


def snapshot():
    return {
        "status": "CONNECTED",
        "connection_status": "CONNECTED",
        "config": {
            "enabled": True,
            "mode": "PAPER",
            "mode_valid": True,
            "host": "127.0.0.1",
            "port": 4002,
            "port_valid": True,
            "endpoint_safe": True,
            "read_only": True,
            "client_id": 82,
            "client_id_valid": True,
        },
        "official_ibapi_available": True,
        "order_submission_hard_blocked": True,
        "broker_mutation_surface_hard_blocked": True,
        "open_order_observation_mode": (
            "REQ_ALL_OPEN_ORDERS_NON_BINDING"
        ),
        "client_zero_binding_hard_blocked": True,
        "gateway_read_only_configuration_independently_attested": True,
        "live_trading_allowed": False,
        "account_count": 1,
        "accounts": [ACCOUNT],
        "paper_account_guard": {
            "allowlist_configured": True,
            "managed_account_received": True,
            "account_count": 1,
            "all_accounts_allowlisted": True,
            "paper_account_verified": True,
            "verified_account_fingerprints": [ACCOUNT],
            "reason": "PAPER_ACCOUNT_VERIFIED",
        },
        "account_summary_account_fingerprints": [ACCOUNT],
        "account_summary": {
            "NetLiquidation": {"value": 100000.0, "currency": "USD"},
            "TotalCashValue": {"value": 50000.0, "currency": "USD"},
            "AvailableFunds": {"value": 45000.0, "currency": "USD"},
            "BuyingPower": {"value": 180000.0, "currency": "USD"},
        },
        "positions": [],
        "open_orders": [],
        "order_status": [],
        "executions": [],
        "requests_complete": {
            "managed_accounts": True,
            "account_summary": True,
            "positions": True,
            "open_orders": True,
            "executions": True,
        },
    }


def proof():
    broker_snapshot = snapshot()
    return {
        "evidence_run_id": RUN_ID,
        "probe_stage": "POST_REVIEW_PROBE",
        "run_mode": {
            "mode": "READ_ONLY",
            "live_execution_allowed": False,
            "paper_order_submission_requested": False,
        },
        "runtime_provenance": {
            "verified": True,
            "runtime_cloud_identity": {
                "project_id": "project-ce9773ef-6814-469c-92b",
                "instance_name": "aurora-trading-vps",
                "zone": "europe-west3-a",
                "instance_id": INSTANCE_ID,
            },
            "g0_runtime_proof_sha256": "a" * 64,
            "failure_reasons": [],
            **safe_permissions(),
        },
        "snapshot": broker_snapshot,
        "gateway_read_only_attestation": {
            "status": "VERIFIED",
            "verified": True,
            "gateway_read_only_configuration_independently_attested": True,
            "failure_reasons": [],
            **safe_permissions(),
        },
        "readiness": evaluate_ibkr_paper_readiness(
            broker_snapshot,
            [],
        ),
    }


class G2PostReviewStatusTests(unittest.TestCase):
    def test_valid_proof_advances_only_to_g3(self):
        result = evaluate_post_review_g2_status(
            RUN_ID,
            proof(),
        )

        self.assertEqual(
            result["status"],
            "READY_FOR_G3_MARKET_DATA_PROBE",
        )
        self.assertEqual(
            result["next_action"],
            "RUN_G3_VERIFIED_REALTIME_MARKET_DATA_PROBE",
        )
        self.assertFalse(result["human_action_required"])
        self.assertEqual(
            result["gcp_instance_id"],
            INSTANCE_ID,
        )
        for name in safe_permissions():
            self.assertIs(result[name], False)

    def test_pre_review_probe_stage_blocks(self):
        value = proof()
        value["probe_stage"] = "PRE_REVIEW_DIAGNOSTIC"
        result = evaluate_post_review_g2_status(
            RUN_ID,
            value,
        )
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn(
            "G2_POST_REVIEW_PROBE_STAGE_INVALID",
            result["failure_reasons"],
        )

    def test_mismatched_run_id_blocks(self):
        value = proof()
        value["evidence_run_id"] = (
            "22222222-2222-4222-8222-222222222222"
        )

        result = evaluate_post_review_g2_status(
            RUN_ID,
            value,
        )

        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn(
            "G2_EVIDENCE_RUN_MISMATCH",
            result["failure_reasons"],
        )

    def test_unverified_attestation_blocks(self):
        value = proof()
        value["gateway_read_only_attestation"][
            "status"
        ] = "BLOCKED"
        value["gateway_read_only_attestation"][
            "verified"
        ] = False
        value["gateway_read_only_attestation"][
            "gateway_read_only_configuration_independently_attested"
        ] = False

        result = evaluate_post_review_g2_status(
            RUN_ID,
            value,
        )

        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn(
            "GATEWAY_READ_ONLY_ATTESTATION_NOT_VERIFIED",
            result["failure_reasons"],
        )

    def test_forged_stored_ready_cannot_hide_broken_snapshot(self):
        value = proof()
        value["snapshot"]["account_summary"].pop(
            "TotalCashValue"
        )
        value["readiness"]["readiness"] = (
            "READY_FOR_PAPER_READ_ONLY"
        )
        value["readiness"]["required_failure_count"] = 0

        result = evaluate_post_review_g2_status(
            RUN_ID,
            value,
        )

        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn(
            "G2_RECOMPUTED_READINESS_NOT_CLEAN",
            result["failure_reasons"],
        )

    def test_permission_regression_in_provenance_blocks(self):
        value = proof()
        value["runtime_provenance"][
            "paper_order_submission_allowed"
        ] = True

        result = evaluate_post_review_g2_status(
            RUN_ID,
            value,
        )

        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn(
            "G2_RUNTIME_PROVENANCE_INVALID",
            result["failure_reasons"],
        )

    def test_permission_regression_in_attestation_blocks(self):
        value = proof()
        value["gateway_read_only_attestation"][
            "paper_order_submission_allowed"
        ] = True

        result = evaluate_post_review_g2_status(
            RUN_ID,
            value,
        )

        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn(
            "GATEWAY_READ_ONLY_ATTESTATION_NOT_VERIFIED",
            result["failure_reasons"],
        )

    def test_stored_required_check_tamper_blocks(self):
        value = proof()
        value["readiness"] = copy.deepcopy(
            value["readiness"]
        )
        for item in value["readiness"]["checks"]:
            if item["required"] is True:
                item["passed"] = False
                break

        result = evaluate_post_review_g2_status(
            RUN_ID,
            value,
        )

        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn(
            "G2_REQUIRED_CHECKS_NOT_CLEAN",
            result["failure_reasons"],
        )


if __name__ == "__main__":
    unittest.main()
