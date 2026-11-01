import unittest
from engines.paper_portfolio_risk import evaluate_portfolio_intent


def order():
    return {"symbol": "NVDA", "side": "BUY", "order_type": "LMT",
            "quantity": 1, "limit_price": 100.0,
            "idempotency_key": "paper-risk-0001"}


def env():
    return {"mode": "PAPER", "live_trading_allowed": False,
            "broker_read_only": True, "paper_account_verified": True,
            "kill_switch_engaged": True}


def snapshot():
    return {"snapshot_verified": True, "snapshot_fresh": True,
            "equity_usd": 1000, "gross_exposure_usd": 300,
            "pending_notional_usd": 100, "known_idempotency_keys": []}


class TestPortfolioRisk(unittest.TestCase):
    def check(self, portfolio, reason, intent=None, context=None):
        result = evaluate_portfolio_intent(
            intent if intent is not None else order(),
            context if context is not None else env(), portfolio)
        self.assertEqual(result["reason"], reason)
        self.assertIs(result["paper_order_submission_allowed"], False)
        self.assertIs(result["live_trading_allowed"], False)
        return result

    def test_safe_diagnostic_still_denies_execution(self):
        result = self.check(snapshot(), "PORTFOLIO_DIAGNOSTIC_ONLY_NO_EXECUTION")
        self.assertEqual(result["status"], "VALIDATED_READ_ONLY")

    def test_missing_snapshot_blocks(self):
        self.check(None, "MISSING_PORTFOLIO_SNAPSHOT")

    def test_stale_snapshot_blocks(self):
        p = snapshot()
        p["snapshot_fresh"] = False
        self.check(p, "UNVERIFIED_OR_STALE_PORTFOLIO")

    def test_unverified_snapshot_blocks(self):
        p = snapshot()
        p["snapshot_verified"] = False
        self.check(p, "UNVERIFIED_OR_STALE_PORTFOLIO")

    def test_duplicate_key_blocks(self):
        p = snapshot()
        p["known_idempotency_keys"] = ["paper-risk-0001"]
        self.check(p, "DUPLICATE_ORDER_INTENT")

    def test_corrupted_history_blocks(self):
        p = snapshot()
        p["known_idempotency_keys"] = ["a", "a"]
        self.check(p, "CORRUPTED_IDEMPOTENCY_HISTORY")

    def test_pending_orders_count_toward_exposure(self):
        p = snapshot()
        p["pending_notional_usd"] = 650
        self.check(p, "EXPOSURE_EXCEEDS_EQUITY")

    def test_invalid_values_block(self):
        for bad in (-1, float("nan"), float("inf"), True):
            with self.subTest(value=str(bad)):
                p = snapshot()
                p["equity_usd"] = bad
                self.check(p, "INVALID_PORTFOLIO_VALUES")

    def test_sell_does_not_release_unverified_exposure(self):
        p = snapshot()
        p["gross_exposure_usd"] = 1001
        o = order()
        o["side"] = "SELL"
        self.check(p, "EXPOSURE_EXCEEDS_EQUITY", intent=o)

    def test_live_mode_still_blocks(self):
        c = env()
        c["mode"] = "LIVE"
        self.check(snapshot(), "UNSAFE_MODE", context=c)


if __name__ == "__main__":
    unittest.main()
