"""G7 offline regression tests for read-only IBKR readiness.

No broker, network connection, or order submission is used.
"""
import unittest

from engines.ibkr_paper_readiness_engine import evaluate_ibkr_paper_readiness


def snapshot():
    account = "IBKR-TESTTOKEN"
    return {
        "status": "CONNECTED",
        "config": {
            "mode": "PAPER",
            "mode_valid": True,
            "endpoint_safe": True,
            "read_only": True,
            "client_id": 82,
            "client_id_valid": True,
        },
        "paper_account_guard": {
            "allowlist_configured": True,
            "paper_account_verified": True,
            "verified_account_fingerprints": [account],
            "account_count": 1,
        },
        "accounts": [account],
        "account_count": 1,
        "account_summary_account_fingerprints": [account],
        "account_summary": {
            key: {"value": value} for key, value in {
                "NetLiquidation": 10000, "TotalCashValue": 9000,
                "AvailableFunds": 8000, "BuyingPower": 16000,
            }.items()
        },
        "official_ibapi_available": True,
        "order_submission_hard_blocked": True,
        "broker_mutation_surface_hard_blocked": True,
        "open_order_observation_mode": "REQ_ALL_OPEN_ORDERS_NON_BINDING",
        "client_zero_binding_hard_blocked": True,
        "gateway_read_only_configuration_independently_attested": True,
        "live_trading_allowed": False,
        "requests_complete": {
            "managed_accounts": True, "account_summary": True,
            "positions": True, "open_orders": True,
        },
        "positions": [],
        "open_orders": [],
    }


class G7ReadOnlyReadinessTests(unittest.TestCase):
    def check(self, data):
        return evaluate_ibkr_paper_readiness(data, [])

    def test_valid_snapshot_is_read_only_not_order_ready(self):
        result = self.check(snapshot())
        self.assertEqual(result["readiness"], "READY_FOR_PAPER_READ_ONLY")
        self.assertFalse(result["paper_order_submission_allowed"])
        self.assertFalse(result["live_execution_allowed"])

    def test_missing_gateway_read_only_attestation_blocks(self):
        data = snapshot()
        data.pop("gateway_read_only_configuration_independently_attested")
        result = self.check(data)
        self.assertEqual(result["readiness"], "NOT_READY")
        self.assertTrue(result["diagnostic_read_only_ready"])
        self.assertEqual(
            result["next_milestone"],
            "INDEPENDENT_GATEWAY_READ_ONLY_ATTESTATION",
        )

    def test_false_gateway_read_only_attestation_blocks(self):
        data = snapshot()
        data["gateway_read_only_configuration_independently_attested"] = False
        result = self.check(data)
        self.assertEqual(result["readiness"], "NOT_READY")
        self.assertTrue(result["diagnostic_read_only_ready"])

    def test_missing_mutation_hard_block_blocks(self):
        data = snapshot()
        data["broker_mutation_surface_hard_blocked"] = False
        self.assertEqual(self.check(data)["readiness"], "NOT_READY")

    def test_binding_open_order_mode_blocks(self):
        data = snapshot()
        data["open_order_observation_mode"] = "REQ_OPEN_ORDERS_BINDING"
        self.assertEqual(self.check(data)["readiness"], "NOT_READY")

    def test_client_zero_blocks(self):
        data = snapshot()
        data["config"]["client_id"] = 0
        data["config"]["client_id_valid"] = False
        self.assertEqual(self.check(data)["readiness"], "NOT_READY")

    def test_live_mode_blocks(self):
        data = snapshot()
        data["config"]["mode"] = "LIVE"
        self.assertEqual(self.check(data)["readiness"], "NOT_READY")

    def test_unverified_account_blocks(self):
        data = snapshot()
        data["paper_account_guard"]["paper_account_verified"] = False
        self.assertEqual(self.check(data)["readiness"], "NOT_READY")

    def test_account_summary_mismatch_blocks(self):
        data = snapshot()
        data["account_summary_account_fingerprints"] = ["IBKR-OTHER"]
        self.assertEqual(self.check(data)["readiness"], "NOT_READY")

    def test_incomplete_positions_blocks(self):
        data = snapshot()
        data["requests_complete"]["positions"] = False
        self.assertEqual(self.check(data)["readiness"], "NOT_READY")

    def test_foreign_order_account_blocks(self):
        data = snapshot()
        data["open_orders"] = [{"account": "IBKR-OTHER"}]
        self.assertEqual(self.check(data)["readiness"], "NOT_READY")

    def test_missing_cash_blocks(self):
        data = snapshot()
        del data["account_summary"]["TotalCashValue"]
        self.assertEqual(self.check(data)["readiness"], "NOT_READY")

    def test_non_finite_required_account_metrics_block(self):
        for metric in ("NetLiquidation", "TotalCashValue", "AvailableFunds"):
            for value in (float("nan"), float("inf"), float("-inf"), True, False):
                with self.subTest(metric=metric, value=value):
                    data = snapshot()
                    data["account_summary"][metric]["value"] = value
                    self.assertEqual(self.check(data)["readiness"], "NOT_READY")

    def test_non_finite_account_count_blocks(self):
        data = snapshot()
        data["account_count"] = float("nan")
        self.assertEqual(self.check(data)["readiness"], "NOT_READY")

    def test_malformed_nested_snapshot_sections_fail_closed(self):
        for key, value in (
            ("config", []),
            ("paper_account_guard", "invalid"),
            ("account_summary", []),
            ("requests_complete", "invalid"),
            ("positions", "invalid"),
            ("open_orders", {"not": "a-list"}),
        ):
            with self.subTest(key=key):
                data = snapshot()
                data[key] = value
                self.assertEqual(self.check(data)["readiness"], "NOT_READY")

    def test_malformed_account_fingerprint_payloads_fail_closed(self):
        for key, value in (
            ("verified_account_fingerprints", "IBKR-TESTTOKEN"),
            ("verified_account_fingerprints", [123]),
            ("verified_account_fingerprints", []),
        ):
            with self.subTest(key=key, value=value):
                data = snapshot()
                data["paper_account_guard"][key] = value
                self.assertEqual(self.check(data)["readiness"], "NOT_READY")

        data = snapshot()
        data["accounts"] = [123]
        self.assertEqual(self.check(data)["readiness"], "NOT_READY")

        data = snapshot()
        data["account_summary_account_fingerprints"] = [123]
        self.assertEqual(self.check(data)["readiness"], "NOT_READY")

    def test_duplicate_or_count_mismatched_account_identity_blocks(self):
        data = snapshot()
        data["paper_account_guard"]["verified_account_fingerprints"] = [
            "IBKR-TESTTOKEN",
            "IBKR-TESTTOKEN",
        ]
        self.assertEqual(self.check(data)["readiness"], "NOT_READY")

        data = snapshot()
        data["accounts"] = ["IBKR-TESTTOKEN", "IBKR-TESTTOKEN"]
        self.assertEqual(self.check(data)["readiness"], "NOT_READY")

        data = snapshot()
        data["account_summary_account_fingerprints"] = [
            "IBKR-TESTTOKEN",
            "IBKR-TESTTOKEN",
        ]
        self.assertEqual(self.check(data)["readiness"], "NOT_READY")

        data = snapshot()
        data["account_count"] = 2
        self.assertEqual(self.check(data)["readiness"], "NOT_READY")

    def test_non_dict_snapshot_fails_closed(self):
        for data in ([], "invalid", 123, True):
            with self.subTest(data=repr(data)):
                self.assertEqual(self.check(data)["readiness"], "NOT_READY")

    def test_missing_position_or_open_order_payload_blocks(self):
        for key in ("positions", "open_orders"):
            with self.subTest(key=key):
                data = snapshot()
                data.pop(key)
                self.assertEqual(self.check(data)["readiness"], "NOT_READY")

    def test_malformed_position_quantity_or_symbol_blocks(self):
        for row in (
            {"account": "IBKR-TESTTOKEN", "symbol": "", "position": 1},
            {"account": "IBKR-TESTTOKEN", "symbol": "NVDA", "position": float("nan")},
            {"account": "IBKR-TESTTOKEN", "symbol": "NVDA", "position": "not-a-number"},
            {"account": "IBKR-TESTTOKEN", "symbol": "NVDA", "position": True},
        ):
            with self.subTest(row=row):
                data = snapshot()
                data["positions"] = [row]
                self.assertEqual(self.check(data)["readiness"], "NOT_READY")

    def test_malformed_open_order_identity_blocks(self):
        for row in (
            {"account": "IBKR-TESTTOKEN", "symbol": "NVDA", "order_id": -1},
            {"account": "IBKR-TESTTOKEN", "symbol": "", "order_id": 1},
            {"account": "IBKR-TESTTOKEN", "symbol": "NVDA", "order_id": True},
        ):
            with self.subTest(row=row):
                data = snapshot()
                data["open_orders"] = [row]
                self.assertEqual(self.check(data)["readiness"], "NOT_READY")


if __name__ == "__main__":
    unittest.main()
