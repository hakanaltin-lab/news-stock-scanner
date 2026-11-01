import unittest
from engines.paper_intent_preflight import validate_paper_intent


def intent():
    return {"symbol": "NVDA", "side": "BUY", "order_type": "LMT",
            "quantity": 1, "limit_price": 100.0,
            "idempotency_key": "paper-test-0001"}


def context():
    return {"mode": "PAPER", "live_trading_allowed": False,
            "broker_read_only": True, "paper_account_verified": True,
            "kill_switch_engaged": True}


class TestPaperIntentPreflight(unittest.TestCase):
    def check(self, order, environment, expected):
        result = validate_paper_intent(order, environment)
        self.assertEqual(result["reason"], expected)
        self.assertIs(result["paper_order_submission_allowed"], False)
        self.assertIs(result["live_trading_allowed"], False)

    def test_valid_intent_remains_non_executable(self):
        self.check(intent(), context(), "DIAGNOSTIC_ONLY_NO_EXECUTION")

    def test_live_mode_blocks(self):
        env = context()
        env["mode"] = "LIVE"
        self.check(intent(), env, "UNSAFE_MODE")

    def test_missing_read_only_blocks(self):
        env = context()
        env["broker_read_only"] = False
        self.check(intent(), env, "READ_ONLY_GUARD_MISSING")

    def test_missing_paper_account_blocks(self):
        env = context()
        env["paper_account_verified"] = False
        self.check(intent(), env, "PAPER_ACCOUNT_UNVERIFIED")

    def test_disengaged_kill_switch_blocks(self):
        env = context()
        env["kill_switch_engaged"] = False
        self.check(intent(), env, "KILL_SWITCH_NOT_ENGAGED")

    def test_market_order_blocks(self):
        order = intent()
        order["order_type"] = "MKT"
        self.check(order, context(), "UNSUPPORTED_ORDER_TYPE")

    def test_invalid_quantities_block(self):
        for qty in (0, -1, 101, 1.5, True):
            with self.subTest(qty=qty):
                order = intent()
                order["quantity"] = qty
                self.check(order, context(), "INVALID_QUANTITY")

    def test_invalid_prices_block(self):
        for price in (0, -1, float("nan"), float("inf"), True):
            with self.subTest(price=price):
                order = intent()
                order["limit_price"] = price
                self.check(order, context(), "INVALID_LIMIT_PRICE")

    def test_notional_cap_blocks(self):
        order = intent()
        order["quantity"] = 6
        self.check(order, context(), "NOTIONAL_CAP_EXCEEDED")

    def test_missing_idempotency_blocks(self):
        order = intent()
        order.pop("idempotency_key")
        self.check(order, context(), "INVALID_IDEMPOTENCY_KEY")

    def test_invalid_symbol_blocks(self):
        order = intent()
        order["symbol"] = "NVDA;DROP"
        self.check(order, context(), "INVALID_SYMBOL")


if __name__ == "__main__":
    unittest.main()
