"""G7.13 offline regressions for execution market-data fail-closed behavior."""

from datetime import datetime, timedelta, timezone
import unittest

from engines.market_data_quality_gate import (
    evaluate_market_data_for_execution,
)


class ExecutionMarketDataFailClosedTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(
            2026,
            11,
            2,
            12,
            0,
            tzinfo=timezone.utc,
        )
        self.good = {
            "source": "IBKR_REALTIME",
            "market_timestamp": self.now.isoformat(),
            "last_price": 123.45,
            "data_points": 1,
            "data_quality": "AVAILABLE",
            "execution_eligible": True,
            "broker_market_timestamp_verified": True,
        }

    def gate(self, payload=None, **kwargs):
        return evaluate_market_data_for_execution(
            self.good if payload is None else payload,
            now=kwargs.pop("now", self.now),
            **kwargs,
        )

    def test_valid_ibkr_shape_passes_data_gate_only(self):
        result = self.gate()
        self.assertEqual(result["decision"], "PASS")
        self.assertTrue(result["execution_eligible"])

    def test_non_dict_market_data_blocks_without_exception(self):
        for value in (
            None,
            "invalid",
            [1],
            42,
            True,
        ):
            with self.subTest(value=value):
                result = self.gate(payload=value)
                self.assertEqual(result["decision"], "BLOCK")
                self.assertFalse(result["execution_eligible"])

    def test_invalid_reference_clock_never_falls_back_to_wall_clock(self):
        for value in (
            "bad-clock",
            "2026-11-02T12:00:00",
            [],
            True,
        ):
            with self.subTest(value=value):
                result = self.gate(now=value)
                self.assertEqual(result["decision"], "BLOCK")
                self.assertEqual(
                    result["failure_reasons"],
                    ["INVALID_REFERENCE_CLOCK"],
                )

    def test_invalid_max_age_configuration_blocks(self):
        for value in (
            None,
            True,
            False,
            "bad",
            float("nan"),
            float("inf"),
            float("-inf"),
            -1,
            0,
            10.1,
            999999,
        ):
            with self.subTest(value=value):
                result = self.gate(
                    max_age_seconds=value,
                )
                self.assertEqual(result["decision"], "BLOCK")
                self.assertEqual(
                    result["failure_reasons"],
                    ["INVALID_MAX_AGE_SECONDS"],
                )

    def test_invalid_or_non_finite_price_blocks(self):
        for value in (
            True,
            False,
            "not-a-price",
            float("nan"),
            float("inf"),
            float("-inf"),
        ):
            with self.subTest(value=value):
                quote = {
                    **self.good,
                    "last_price": value,
                }
                result = self.gate(payload=quote)
                self.assertEqual(result["decision"], "BLOCK")
                self.assertIn(
                    "positive_price",
                    result["failure_reasons"],
                )

    def test_data_points_requires_positive_plain_integer(self):
        for value in (
            None,
            True,
            False,
            float("nan"),
            float("inf"),
            1.0,
            1.5,
            "1",
            "1.5",
            -1,
            0,
        ):
            with self.subTest(value=value):
                quote = {
                    **self.good,
                    "data_points": value,
                }
                result = self.gate(payload=quote)
                self.assertEqual(result["decision"], "BLOCK")
                self.assertIn(
                    "has_data_points",
                    result["failure_reasons"],
                )

    def test_stale_and_future_quotes_block(self):
        cases = (
            (
                self.now - timedelta(seconds=11),
                "fresh",
            ),
            (
                self.now + timedelta(seconds=3),
                "clock_sane",
            ),
        )
        for stamp, reason in cases:
            with self.subTest(stamp=stamp):
                quote = {
                    **self.good,
                    "market_timestamp": stamp.isoformat(),
                }
                result = self.gate(payload=quote)
                self.assertEqual(result["decision"], "BLOCK")
                self.assertIn(
                    reason,
                    result["failure_reasons"],
                )

    def test_caller_cannot_expand_execution_source_allowlist(self):
        quote = {
            **self.good,
            "source": "YFINANCE_15M",
        }
        result = self.gate(
            payload=quote,
            allowed_sources={"YFINANCE_15M"},
        )
        self.assertEqual(result["decision"], "BLOCK")
        self.assertIn(
            "source_allowed",
            result["failure_reasons"],
        )


if __name__ == "__main__":
    unittest.main()
