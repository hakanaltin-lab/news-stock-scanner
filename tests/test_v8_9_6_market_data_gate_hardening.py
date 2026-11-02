"""Offline execution market data fail-closed regressions."""
import unittest
from datetime import datetime, timezone, timedelta
from engines.market_data_quality_gate import evaluate_market_data_for_execution


class MarketDataGateHardeningTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 2, 12, 0, tzinfo=timezone.utc)
        self.quote = {
            "source": "IBKR_REALTIME",
            "market_timestamp": self.now.isoformat(),
            "last_price": 123.45,
            "data_points": 1,
            "data_quality": "AVAILABLE",
            "execution_eligible": True,
            "broker_market_timestamp_verified": True,
        }

    def test_valid_shape_is_only_data_gate_pass(self):
        self.assertEqual(evaluate_market_data_for_execution(self.quote, now=self.now)["decision"], "PASS")

    def test_invalid_clock_blocks_instead_of_falling_back(self):
        result = evaluate_market_data_for_execution(self.quote, now="bad-clock")
        self.assertEqual(result["decision"], "BLOCK")
        self.assertIn("INVALID_REFERENCE_CLOCK", result["failure_reasons"])

    def test_malformed_market_data_blocks(self):
        for value in ("bad", [1], 42, True):
            with self.subTest(value=value):
                self.assertEqual(evaluate_market_data_for_execution(value, now=self.now)["decision"], "BLOCK")

    def test_non_finite_data_points_blocks(self):
        for value in (float("inf"), float("nan"), True, 1.5, "1.5", -1):
            with self.subTest(value=value):
                quote = {**self.quote, "data_points": value}
                self.assertIn("has_data_points", evaluate_market_data_for_execution(quote, now=self.now)["failure_reasons"])

    def test_invalid_max_age_configuration_blocks(self):
        for value in (None, "bad", float("nan"), float("inf"), -1, 0, 999999):
            with self.subTest(value=value):
                result = evaluate_market_data_for_execution(
                    self.quote, now=self.now, max_age_seconds=value
                )
                self.assertEqual(result["decision"], "BLOCK")
                self.assertIn("INVALID_MAX_AGE_SECONDS", result["failure_reasons"])

    def test_yahoo_never_execution_grade(self):
        quote = {**self.quote, "source": "YFINANCE_15M"}
        self.assertEqual(evaluate_market_data_for_execution(quote, now=self.now)["decision"], "BLOCK")

    def test_stale_and_future_quotes_block(self):
        for offset in (-11, 3):
            quote = {**self.quote, "market_timestamp": (self.now + timedelta(seconds=offset)).isoformat()}
            self.assertEqual(evaluate_market_data_for_execution(quote, now=self.now)["decision"], "BLOCK")


if __name__ == "__main__":
    unittest.main()
