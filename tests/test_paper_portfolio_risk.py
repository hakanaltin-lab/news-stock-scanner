import unittest
from datetime import datetime, timedelta, timezone
from engines.paper_portfolio_risk import evaluate_portfolio_intent


NOW = datetime(2026, 11, 1, 12, 0, 0, tzinfo=timezone.utc)


def order():
    return {"symbol": "NVDA", "side": "BUY", "order_type": "LMT",
            "quantity": 1, "limit_price": 100.0,
            "idempotency_key": "paper-risk-0001"}


def env():
    return {"mode": "PAPER", "live_trading_allowed": False,
            "broker_read_only": True, "paper_account_verified": True,
            "kill_switch_engaged": True,
            "paper_account_fingerprint": "PAPER-REDACTED"}


def pending(symbol="AMD", side="BUY", quantity=1, price=100.0,
            key="existing-pending-0001"):
    return {"symbol": symbol, "side": side, "quantity": quantity,
            "limit_price": price, "idempotency_key": key}


def snapshot():
    return {"snapshot_verified": True, "snapshot_fresh": True,
            "snapshot_generated_at_utc": (NOW - timedelta(seconds=5)).isoformat(),
            "paper_account_fingerprint": "PAPER-REDACTED",
            "equity_usd": 1000, "gross_exposure_usd": 300,
            "pending_notional_usd": 100,
            "pending_orders": [pending()],
            "known_idempotency_keys": []}


class TestPortfolioRisk(unittest.TestCase):
    def check(self, portfolio, reason, intent=None, context=None, now_utc=NOW):
        result = evaluate_portfolio_intent(
            intent if intent is not None else order(),
            context if context is not None else env(), portfolio, now_utc=now_utc)
        self.assertEqual(result["reason"], reason)
        self.assertIs(result["paper_order_submission_allowed"], False)
        self.assertIs(result["live_trading_allowed"], False)
        return result

    def test_safe_diagnostic_still_denies_execution(self):
        result = self.check(snapshot(), "PORTFOLIO_DIAGNOSTIC_ONLY_NO_EXECUTION")
        self.assertEqual(result["status"], "VALIDATED_READ_ONLY")
        self.assertEqual(result["snapshot_age_seconds"], 5.0)
        self.assertEqual(len(result["intent_sha256"]), 64)
        self.assertEqual(result["idempotency_key"], "paper-risk-0001")

    def test_missing_snapshot_blocks(self):
        self.check(None, "MISSING_PORTFOLIO_SNAPSHOT")

    def test_stale_snapshot_flag_blocks(self):
        p = snapshot()
        p["snapshot_fresh"] = False
        self.check(p, "UNVERIFIED_OR_STALE_PORTFOLIO")

    def test_unverified_snapshot_blocks(self):
        p = snapshot()
        p["snapshot_verified"] = False
        self.check(p, "UNVERIFIED_OR_STALE_PORTFOLIO")

    def test_missing_or_mismatched_account_fingerprint_blocks(self):
        for value in (None, "", "LIVE-ACCOUNT", "PAPER-OTHER"):
            with self.subTest(value=value):
                p = snapshot()
                p["paper_account_fingerprint"] = value
                self.check(p, "PORTFOLIO_ACCOUNT_MISMATCH")

    def test_missing_context_account_fingerprint_blocks(self):
        c = env()
        c.pop("paper_account_fingerprint")
        self.check(snapshot(), "PORTFOLIO_ACCOUNT_MISMATCH", context=c)

    def test_invalid_snapshot_timestamp_blocks(self):
        for value in (None, "", "not-a-time", "2026-11-01T12:00:00"):
            with self.subTest(value=value):
                p = snapshot()
                p["snapshot_generated_at_utc"] = value
                self.check(p, "INVALID_SNAPSHOT_TIMESTAMP")

    def test_timestamp_older_than_limit_blocks(self):
        p = snapshot()
        p["snapshot_generated_at_utc"] = (NOW - timedelta(seconds=61)).isoformat()
        self.check(p, "SNAPSHOT_TIMESTAMP_STALE")

    def test_future_timestamp_blocks(self):
        p = snapshot()
        p["snapshot_generated_at_utc"] = (NOW + timedelta(seconds=1)).isoformat()
        self.check(p, "SNAPSHOT_TIMESTAMP_STALE")

    def test_duplicate_key_blocks(self):
        p = snapshot()
        p["known_idempotency_keys"] = ["paper-risk-0001"]
        self.check(p, "DUPLICATE_ORDER_INTENT")

    def test_duplicate_key_against_pending_order_blocks(self):
        p = snapshot()
        p["pending_orders"][0]["idempotency_key"] = "paper-risk-0001"
        self.check(p, "DUPLICATE_ORDER_INTENT")

    def test_corrupted_history_blocks(self):
        p = snapshot()
        p["known_idempotency_keys"] = ["a", "a"]
        self.check(p, "CORRUPTED_IDEMPOTENCY_HISTORY")

    def test_missing_pending_orders_blocks(self):
        p = snapshot()
        p.pop("pending_orders")
        self.check(p, "MISSING_PENDING_ORDER_EVIDENCE")

    def test_pending_notional_mismatch_blocks(self):
        p = snapshot()
        p["pending_notional_usd"] = 99
        self.check(p, "PENDING_NOTIONAL_MISMATCH")

    def test_duplicate_pending_order_idempotency_blocks(self):
        p = snapshot()
        p["pending_orders"] = [pending(), pending(symbol="GOOG")]
        p["pending_notional_usd"] = 200
        self.check(p, "DUPLICATE_PENDING_ORDER_IDEMPOTENCY")

    def test_malformed_pending_order_blocks(self):
        p = snapshot()
        p["pending_orders"] = [{"symbol": "AMD"}]
        p["pending_notional_usd"] = 0
        self.check(p, "INVALID_PENDING_ORDER_IDEMPOTENCY")

    def test_pending_orders_count_toward_exposure(self):
        p = snapshot()
        p["pending_orders"] = [pending(quantity=7)]
        p["pending_notional_usd"] = 700
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
        p["positions_by_symbol"] = {"NVDA": 1}
        o = order()
        o["side"] = "SELL"
        self.check(p, "EXPOSURE_EXCEEDS_EQUITY", intent=o)

    def test_sell_without_positions_blocks(self):
        o = order()
        o["side"] = "SELL"
        self.check(snapshot(), "MISSING_SELL_POSITION_EVIDENCE", intent=o)

    def test_sell_missing_symbol_blocks(self):
        o = order()
        o["side"] = "SELL"
        p = snapshot()
        p["positions_by_symbol"] = {"AMD": 3}
        self.check(p, "UNKNOWN_SELL_POSITION", intent=o)

    def test_sell_pending_quantity_prevents_oversell(self):
        o = order()
        o["side"] = "SELL"
        o["quantity"] = 2
        p = snapshot()
        p["positions_by_symbol"] = {"NVDA": 3}
        p["pending_orders"] = [pending(symbol="NVDA", side="SELL", quantity=2)]
        p["pending_notional_usd"] = 200
        self.check(p, "INSUFFICIENT_AVAILABLE_SHARES", intent=o)

    def test_sell_exact_available_shares_remains_non_executable(self):
        o = order()
        o["side"] = "SELL"
        o["quantity"] = 2
        p = snapshot()
        p["positions_by_symbol"] = {"NVDA": 3}
        p["pending_orders"] = [pending(symbol="NVDA", side="SELL", quantity=1)]
        p["pending_notional_usd"] = 100
        self.check(p, "PORTFOLIO_DIAGNOSTIC_ONLY_NO_EXECUTION", intent=o)

    def test_malformed_positions_block(self):
        o = order()
        o["side"] = "SELL"
        for bad in (-1, True, 1.5):
            with self.subTest(bad=bad):
                p = snapshot()
                p["positions_by_symbol"] = {"NVDA": bad}
                self.check(p, "INVALID_SELL_POSITION_EVIDENCE", intent=o)

    def test_live_mode_still_blocks(self):
        c = env()
        c["mode"] = "LIVE"
        self.check(snapshot(), "UNSAFE_MODE", context=c)


if __name__ == "__main__":
    unittest.main()
