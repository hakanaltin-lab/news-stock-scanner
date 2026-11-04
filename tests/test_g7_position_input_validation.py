"""Regression tests for G7 Paper read-only readiness input validation.

Run: python -m unittest discover -s tests -p 'test_g7_position_input_validation.py'
No broker connection or orders are used.
"""
import unittest

from engines.ibkr_paper_readiness_engine import evaluate_ibkr_paper_readiness


def snapshot(positions=None):
    return {
        "status": "CONNECTED",
        "config": {"mode": "PAPER", "mode_valid": True, "endpoint_safe": True,
                   "read_only": True, "client_id": 82, "client_id_valid": True},
        "paper_account_guard": {
            "allowlist_configured": True, "paper_account_verified": True,
            "verified_account_fingerprints": ["paper-fingerprint"],
            "account_count": 1,
        },
        "accounts": ["paper-fingerprint"],
        "account_count": 1,
        "account_summary_account_fingerprints": ["paper-fingerprint"],
        "gateway_read_only_configuration_independently_attested": True,
        "order_submission_hard_blocked": True,
        "broker_mutation_surface_hard_blocked": True,
        "open_order_observation_mode": "REQ_ALL_OPEN_ORDERS_NON_BINDING",
        "live_trading_allowed": False,
        "official_ibapi_available": True,
        "requests_complete": {"managed_accounts": True, "account_summary": True,
                              "positions": True, "open_orders": True},
        "account_summary": {
            key: {"value": "1000"} for key in
            ("NetLiquidation", "TotalCashValue", "AvailableFunds", "BuyingPower")
        },
        "open_orders": [],
        "positions": [] if positions is None else positions,
    }


def position(**changes):
    row = {"account": "paper-fingerprint", "symbol": "AAPL",
           "security_type": "STK", "currency": "USD",
           "con_id": 265598, "position": 2}
    row.update(changes)
    return row


def checks(result):
    return {item["check"]: item["passed"] for item in result["checks"]}


class G7PositionInputValidationTests(unittest.TestCase):
    def test_blocked_reconciliation_is_not_reported_as_observed(self):
        result = evaluate_ibkr_paper_readiness(
            snapshot([position(security_type="OPT")]),
            [{"ticker": "AAPL", "shares": 2}],
        )
        self.assertEqual(
            result["position_sync"]["status"],
            "BLOCKED_INVALID_POSITION_INPUT",
        )
        self.assertFalse(checks(result)["portfolio_sync_observed"])

    def test_valid_stock_position_payload(self):
        result = evaluate_ibkr_paper_readiness(snapshot([position()]),
                                               [{"ticker": "AAPL", "shares": "2"}])
        self.assertTrue(checks(result)["position_instruments_unambiguous"])
        self.assertTrue(checks(result)["portfolio_quantities_and_symbols_valid"])
        self.assertTrue(result["position_sync"]["all_positions_match"])

    def test_missing_portfolio_quantity_blocks(self):
        result = evaluate_ibkr_paper_readiness(snapshot(),
                                               [{"ticker": "AAPL"}])
        self.assertEqual(result["readiness"], "NOT_READY")
        self.assertFalse(checks(result)["portfolio_quantities_and_symbols_valid"])
        self.assertFalse(result["position_sync"]["all_positions_match"])

    def test_nonfinite_portfolio_quantity_blocks(self):
        for bad in ("nan", "inf", True, "invalid"):
            with self.subTest(bad=bad):
                result = evaluate_ibkr_paper_readiness(
                    snapshot(), [{"ticker": "AAPL", "shares": bad}])
                self.assertEqual(result["readiness"], "NOT_READY")

    def test_duplicate_portfolio_symbols_block(self):
        result = evaluate_ibkr_paper_readiness(
            snapshot(), [{"ticker": "AAPL", "shares": 1},
                         {"ticker": "aapl", "shares": 1}])
        self.assertFalse(checks(result)["portfolio_quantities_and_symbols_valid"])
        self.assertFalse(result["position_sync"]["all_positions_match"])
        self.assertEqual(result["readiness"], "NOT_READY")

    def test_wrong_account_blocks(self):
        result = evaluate_ibkr_paper_readiness(
            snapshot([position(account="other-account")]),
            [{"ticker": "AAPL", "shares": 2}])
        self.assertFalse(checks(result)["position_instruments_unambiguous"])
        self.assertFalse(result["position_sync"]["all_positions_match"])
        self.assertEqual(result["readiness"], "NOT_READY")

    def test_non_stock_or_non_usd_blocks(self):
        for change in ({"security_type": "OPT"}, {"currency": "EUR"}):
            with self.subTest(change=change):
                result = evaluate_ibkr_paper_readiness(
                    snapshot([position(**change)]),
                    [{"ticker": "AAPL", "shares": 2}])
                self.assertFalse(checks(result)["position_instruments_unambiguous"])
                self.assertEqual(result["readiness"], "NOT_READY")

    def test_duplicate_broker_identity_blocks(self):
        result = evaluate_ibkr_paper_readiness(
            snapshot([position(position=1), position(position=1)]),
            [{"ticker": "AAPL", "shares": 2}])
        self.assertFalse(checks(result)["position_instruments_unambiguous"])
        self.assertEqual(result["readiness"], "NOT_READY")

    def test_missing_or_invalid_con_id_blocks(self):
        for bad in (None, 0, -1, True, "265598", 265598.0):
            with self.subTest(bad=bad):
                result = evaluate_ibkr_paper_readiness(
                    snapshot([position(con_id=bad)]),
                    [{"ticker": "AAPL", "shares": 2}],
                )
                self.assertFalse(checks(result)["position_instruments_unambiguous"])
                self.assertFalse(result["position_sync"]["all_positions_match"])
                self.assertEqual(result["readiness"], "NOT_READY")

    def test_same_symbol_with_distinct_con_ids_blocks(self):
        result = evaluate_ibkr_paper_readiness(
            snapshot([
                position(con_id=265598, position=1),
                position(con_id=999001, position=1),
            ]),
            [{"ticker": "AAPL", "shares": 2}],
        )
        self.assertFalse(checks(result)["position_instruments_unambiguous"])
        self.assertEqual(result["readiness"], "NOT_READY")

    def test_same_con_id_with_distinct_symbols_blocks(self):
        result = evaluate_ibkr_paper_readiness(
            snapshot([
                position(symbol="AAPL", con_id=265598, position=1),
                position(symbol="MSFT", con_id=265598, position=1),
            ]),
            [{"ticker": "AAPL", "shares": 1},
             {"ticker": "MSFT", "shares": 1}],
        )
        self.assertFalse(checks(result)["position_instruments_unambiguous"])
        self.assertEqual(result["readiness"], "NOT_READY")

    def test_missing_broker_quantity_blocks(self):
        result = evaluate_ibkr_paper_readiness(
            snapshot([position(position=None)]),
            [{"ticker": "AAPL", "shares": 0}])
        self.assertFalse(checks(result)["positions_payload_valid"])
        self.assertFalse(result["position_sync"]["all_positions_match"])
        self.assertEqual(result["readiness"], "NOT_READY")

    def test_incomplete_position_snapshot_blocks(self):
        data = snapshot()
        data["requests_complete"]["positions"] = False
        result = evaluate_ibkr_paper_readiness(data, [])
        self.assertEqual(result["readiness"], "NOT_READY")
        self.assertFalse(checks(result)["positions_snapshot_complete"])
        self.assertFalse(result["position_sync"]["all_positions_match"])

    def test_valid_empty_portfolio_is_not_a_broker_error(self):
        result = evaluate_ibkr_paper_readiness(snapshot(), [])
        self.assertTrue(checks(result)["portfolio_quantities_and_symbols_valid"])
        self.assertTrue(checks(result)["position_instruments_unambiguous"])
        self.assertTrue(result["position_sync"]["all_positions_match"])


if __name__ == "__main__":
    unittest.main()
