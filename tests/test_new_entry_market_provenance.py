"""Fail-closed regression for allocated new entries without verified market provenance.

Read-only: no broker calls, network data, or order execution.
"""
import unittest
from unittest.mock import patch

from engines.recommendation_performance_engine import extract_snapshot_signals


class NewEntryMarketProvenanceTests(unittest.TestCase):
    def snapshot(self, top_actionable):
        return {
            "generated": "2026-11-06T15:00:00+00:00",
            "scanner_version": "TEST",
            "market_regime": {"market_date": "2026-11-06"},
            "portfolio": [],
            "capital_allocation": {
                "allocation_plan": [{
                    "ticker": "TEST",
                    "action": "BUY",
                    "allocation_status": "ALLOCATE",
                    "price": 100.0,
                }]
            },
            "opportunity_analysis": {"top_actionable": top_actionable},
        }

    def test_missing_source_must_not_be_journaled(self):
        self.assertEqual(extract_snapshot_signals(self.snapshot([])), [])

    def test_unverified_source_must_not_be_journaled(self):
        source = {"ticker": "TEST", "market": {
            "data_quality": "FALLBACK", "last_price": 100.0}}
        self.assertEqual(extract_snapshot_signals(self.snapshot([source])), [])

    def test_verified_live_source_is_allowed(self):
        source = {"ticker": "TEST", "market": {
            "data_quality": "LIVE", "last_price": 100.0}}
        records = extract_snapshot_signals(self.snapshot([source]))
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["ticker"], "TEST")


if __name__ == "__main__":
    unittest.main()
