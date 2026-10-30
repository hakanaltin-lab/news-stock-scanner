"""Execution eligibility must fail closed under malformed or research-only data."""
import unittest
from datetime import datetime, timezone, timedelta
from engines.market_data_quality_gate import evaluate_market_data_for_execution


class MarketDataExecutionGateTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 30, 12, 0, tzinfo=timezone.utc)
        self.good = {
            "source": "IBKR_REALTIME",
            "market_timestamp": (self.now - timedelta(seconds=1)).isoformat(),
            "last_price": 100.0,
            "data_quality": "AVAILABLE",
            "data_points": 1,
            "execution_eligible": True,
        }

    def gate(self, **changes):
        data = dict(self.good, **changes)
        return evaluate_market_data_for_execution(data, now=self.now)

    def test_valid_broker_quote(self):
        self.assertEqual(self.gate()["decision"], "PASS")

    def test_research_data_cannot_be_enabled(self):
        result = self.gate(source="YFINANCE_15M", execution_eligible=False)
        self.assertEqual(result["decision"], "BLOCK")

    def test_explicit_false_blocks_even_ibkr(self):
        self.assertEqual(self.gate(execution_eligible=False)["decision"], "BLOCK")

    def test_missing_flag_blocks(self):
        data = dict(self.good)
        data.pop("execution_eligible")
        self.assertEqual(evaluate_market_data_for_execution(data, now=self.now)["decision"], "BLOCK")

    def test_naive_time_blocks(self):
        self.assertEqual(self.gate(market_timestamp="2026-10-30T12:00:00")["decision"], "BLOCK")

    def test_future_time_blocks(self):
        value = (self.now + timedelta(seconds=3)).isoformat()
        self.assertEqual(self.gate(market_timestamp=value)["decision"], "BLOCK")

    def test_stale_quote_blocks(self):
        value = (self.now - timedelta(seconds=11)).isoformat()
        self.assertEqual(self.gate(market_timestamp=value)["decision"], "BLOCK")

    def test_nan_price_blocks(self):
        self.assertEqual(self.gate(last_price=float("nan"))["decision"], "BLOCK")

    def test_custom_source_cannot_override_allowlist(self):
        result = evaluate_market_data_for_execution(
            dict(self.good, source="YFINANCE_15M"), now=self.now,
            allowed_sources={"YFINANCE_15M"},
        )
        self.assertEqual(result["decision"], "BLOCK")


if __name__ == "__main__":
    unittest.main()
