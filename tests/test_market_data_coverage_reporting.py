"""Every portfolio symbol must have an explicit market-data coverage record."""

import unittest

from main import (
    build_market_data_coverage_record,
    summarize_market_data_coverage,
)


class MarketDataCoverageReportingTests(unittest.TestCase):
    def test_research_quote_is_reported_without_execution_promotion(self):
        record = build_market_data_coverage_record(
            "NVDA",
            {
                "source": "YFINANCE_15M",
                "data_scope": "RESEARCH_ONLY",
                "data_quality": "AVAILABLE",
                "market_timestamp": "2026-10-30T12:00:00+00:00",
                "prices": [100.0, 101.0],
                "volumes": [100, 120],
                "data_points": 2,
                "execution_eligible": False,
            },
            {
                "decision": "BLOCK",
                "failure_reasons": [
                    "source_allowed",
                    "explicit_execution_eligibility",
                ],
            },
        )

        self.assertEqual(record["status"], "AVAILABLE_FOR_RESEARCH")
        self.assertIs(record["analysis_eligible"], True)
        self.assertIs(record["execution_eligible"], False)
        self.assertEqual(record["source"], "YFINANCE_15M")

    def test_missing_quote_is_never_silently_lost(self):
        record = build_market_data_coverage_record(
            "AMD",
            {
                "source": "YFINANCE_15M",
                "data_quality": "ERROR",
                "prices": [],
                "volumes": [],
                "error": "provider unavailable",
            },
            {
                "decision": "BLOCK",
                "failure_reasons": ["positive_price", "has_data_points"],
            },
        )

        self.assertEqual(record["ticker"], "AMD")
        self.assertEqual(record["status"], "BLOCKED_NO_USABLE_QUOTE")
        self.assertIs(record["analysis_eligible"], False)
        self.assertIs(record["execution_eligible"], False)
        self.assertEqual(record["provider_error"], "provider unavailable")

    def test_summary_reconciles_expected_and_reported_symbols(self):
        records = [
            {"analysis_eligible": True, "execution_eligible": False},
            {"analysis_eligible": False, "execution_eligible": False},
        ]
        summary = summarize_market_data_coverage(records, expected_symbols=2)

        self.assertEqual(summary["reported_symbols"], 2)
        self.assertEqual(summary["analysis_eligible_symbols"], 1)
        self.assertEqual(summary["blocked_symbols"], 1)
        self.assertEqual(summary["execution_eligible_symbols"], 0)
        self.assertIs(summary["complete_reporting"], True)
        self.assertIs(summary["paper_order_submission_allowed"], False)
        self.assertIs(summary["live_execution_allowed"], False)


if __name__ == "__main__":
    unittest.main()
