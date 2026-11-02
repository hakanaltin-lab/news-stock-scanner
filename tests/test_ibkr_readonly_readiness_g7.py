"""G7 offline regression tests for read-only IBKR readiness.

No broker, network connection, or order submission is used.
"""
import unittest

from engines.ibkr_paper_readiness_engine import evaluate_ibkr_paper_readiness


def snapshot():
    account = "IBKR-TESTTOKEN"
    return {
        "status": "CONNECTED",
        "config": {"mode": "PAPER", "mode_valid": True, "endpoint_safe": True, "read_only": True},
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


if __name__ == "__main__":
    unittest.main()
