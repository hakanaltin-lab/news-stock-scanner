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
        return result

    def test_valid_intent_remains_non_executable_and_digest_bound(self):
        result = self.check(intent(), context(), "DIAGNOSTIC_ONLY_NO_EXECUTION")
        self.assertEqual(result["status"], "VALIDATED_READ_ONLY")
        self.assertEqual(len(result["intent_sha256"]), 64)
        self.assertTrue(all(c in "0123456789abcdef" for c in result["intent_sha256"]))
        self.assertEqual(result["order_type"], "LMT")
        self.assertEqual(result["idempotency_key"], "paper-test-0001")

    def test_semantically_equal_price_has_same_digest(self):
        a = intent()
        b = intent()
        a["limit_price"] = 100
        b["limit_price"] = 100.0
        self.assertEqual(
            validate_paper_intent(a, context())["intent_sha256"],
            validate_paper_intent(b, context())["intent_sha256"],
        )

    def test_execution_relevant_mutation_changes_digest(self):
        base = validate_paper_intent(intent(), context())["intent_sha256"]
        for field, value in (("symbol", "AMD"), ("side", "SELL"),
                             ("quantity", 2), ("limit_price", 101.0),
                             ("idempotency_key", "paper-test-0002")):
            with self.subTest(field=field):
                changed = intent()
                changed[field] = value
                self.assertNotEqual(
                    validate_paper_intent(changed, context())["intent_sha256"],
                    base,
                )

    def test_extra_or_missing_fields_block(self):
        extra = intent()
        extra["note"] = "ignored-metadata"
        self.check(extra, context(), "INVALID_INTENT_SCHEMA")
        missing = intent()
        missing.pop("order_type")
        self.check(missing, context(), "INVALID_INTENT_SCHEMA")

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

    def test_missing_idempotency_blocks_via_schema(self):
        order = intent()
        order.pop("idempotency_key")
        self.check(order, context(), "INVALID_INTENT_SCHEMA")

    def test_invalid_symbol_blocks(self):
        order = intent()
        order["symbol"] = "NVDA;DROP"
        self.check(order, context(), "INVALID_SYMBOL")


if __name__ == "__main__":
    unittest.main()
