"""Regression tests for allocated new-entry provenance (journal only)."""
import unittest

from engines.recommendation_performance_engine import extract_snapshot_signals


def snapshot(source=None, price=100):
    return {
        "generated": "2026-11-07T10:00:00+00:00",
        "scanner_version": "test",
        "capital_allocation": {
            "allocation_plan": [
                {"ticker": "AAPL", "action": "BUY",
                 "allocation_status": "ALLOCATE", "price": price}
            ]
        },
        "opportunity_analysis": {
            "top_actionable": [] if source is None else [source]
        },
    }


class AllocatedEntryProvenanceTests(unittest.TestCase):
    def test_missing_source_rejected(self):
        self.assertEqual(extract_snapshot_signals(snapshot()), [])

    def test_empty_source_rejected(self):
        self.assertEqual(
            extract_snapshot_signals(snapshot({"ticker": "AAPL"})), []
        )

    def test_non_live_source_rejected(self):
        source = {"ticker": "AAPL", "market": {
            "data_quality": "STALE", "last_price": 100}}
        self.assertEqual(extract_snapshot_signals(snapshot(source)), [])

    def test_unmatched_source_rejected(self):
        source = {"ticker": "MSFT", "market": {
            "data_quality": "LIVE", "last_price": 100}}
        self.assertEqual(extract_snapshot_signals(snapshot(source)), [])

    def test_mismatched_allocation_price_rejected(self):
        source = {"ticker": "AAPL", "market": {
            "data_quality": "LIVE", "last_price": 100}}
        self.assertEqual(
            extract_snapshot_signals(snapshot(source, price=105)), []
        )

    def test_nonfinite_allocation_price_rejected(self):
        source = {"ticker": "AAPL", "market": {
            "data_quality": "LIVE", "last_price": 100}}
        self.assertEqual(
            extract_snapshot_signals(snapshot(source, price=float("nan"))), []
        )

    def test_nonfinite_source_price_rejected(self):
        source = {"ticker": "AAPL", "market": {
            "data_quality": "LIVE", "last_price": float("inf")}}
        self.assertEqual(extract_snapshot_signals(snapshot(source)), [])

    def test_verified_source_accepted(self):
        source = {"ticker": "AAPL", "market": {
            "data_quality": "LIVE", "last_price": 100}}
        records = extract_snapshot_signals(snapshot(source))
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["ticker"], "AAPL")
        self.assertEqual(records[0]["source"], "NEW_ENTRY")


if __name__ == "__main__":
    unittest.main()
