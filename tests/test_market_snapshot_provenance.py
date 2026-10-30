"""Regression tests: research quotes must not be mislabeled as execution data."""

import unittest
from engines.market_data_engine import build_market_snapshot


class MarketDataProvenanceTests(unittest.TestCase):
    def test_yahoo_research_data_is_not_execution_eligible(self):
        metadata = {
            "source": "YFINANCE_15M",
            "data_scope": "RESEARCH_ONLY",
            "data_quality": "AVAILABLE",
            "market_timestamp": "2026-10-30T12:00:00+00:00",
            "execution_eligible": False,
        }
        snapshot = build_market_snapshot(
            "TEST", [100.0, 101.0], [100, 120], metadata=metadata
        )
        self.assertEqual(snapshot["source"], "YFINANCE_15M")
        self.assertEqual(snapshot["data_scope"], "RESEARCH_ONLY")
        self.assertEqual(snapshot["data_quality"], "AVAILABLE")
        self.assertEqual(
            snapshot["market_timestamp"], "2026-10-30T12:00:00+00:00"
        )
        self.assertIs(snapshot["execution_eligible"], False)

    def test_missing_provenance_fails_closed(self):
        snapshot = build_market_snapshot("TEST", [100], [100])
        self.assertEqual(snapshot["data_quality"], "UNVERIFIED")
        self.assertIsNone(snapshot["source"])
        self.assertIs(snapshot["execution_eligible"], False)


if __name__ == "__main__":
    unittest.main()
