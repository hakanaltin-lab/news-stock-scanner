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

    def test_zero_allocation_price_rejected(self):
        source = {"ticker": "AAPL", "market": {
            "data_quality": "LIVE", "last_price": 100}}
        self.assertEqual(
            extract_snapshot_signals(snapshot(source, price=0)), []
        )

    def test_tiny_price_rounding_difference_accepted(self):
        source = {"ticker": "AAPL", "market": {
            "data_quality": "LIVE", "last_price": 100}}
        records = extract_snapshot_signals(snapshot(source, price=100.00001))
        self.assertEqual(len(records), 1)

    def test_duplicate_sources_rejected_even_if_prices_match(self):
        source = {"ticker": "AAPL", "market": {
            "data_quality": "LIVE", "last_price": 100}}
        data = snapshot(source)
        data["opportunity_analysis"]["top_actionable"].append(dict(source))
        self.assertEqual(extract_snapshot_signals(data), [])

    def test_conflicting_duplicate_sources_rejected(self):
        source = {"ticker": "AAPL", "market": {
            "data_quality": "LIVE", "last_price": 100}}
        data = snapshot(source)
        data["opportunity_analysis"]["top_actionable"].append({
            "ticker": "AAPL",
            "market": {"data_quality": "LIVE", "last_price": 110}
        })
        self.assertEqual(extract_snapshot_signals(data), [])

    def test_duplicate_executable_allocations_rejected(self):
        source = {"ticker": "AAPL", "market": {
            "data_quality": "LIVE", "last_price": 100}}
        data = snapshot(source)
        data["capital_allocation"]["allocation_plan"].append({
            "ticker": "AAPL", "action": "BUY",
            "allocation_status": "ALLOCATE", "price": 100
        })
        self.assertEqual(extract_snapshot_signals(data), [])

    def test_malformed_allocation_item_ignored(self):
        source = {"ticker": "AAPL", "market": {
            "data_quality": "LIVE", "last_price": 100}}
        data = snapshot(source)
        data["capital_allocation"]["allocation_plan"].append(None)
        self.assertEqual(len(extract_snapshot_signals(data)), 1)

    def test_legacy_duplicate_sources_rejected(self):
        source = {"ticker": "AAPL", "action": "BUY", "market": {
            "data_quality": "LIVE", "last_price": 100}}
        data = snapshot(source)
        data.pop("capital_allocation")
        data["opportunity_analysis"]["top_actionable"].append(dict(source))
        self.assertEqual(extract_snapshot_signals(data), [])

    def test_legacy_unique_source_accepted(self):
        source = {"ticker": "AAPL", "action": "BUY", "market": {
            "data_quality": "LIVE", "last_price": 100}}
        data = snapshot(source)
        data.pop("capital_allocation")
        self.assertEqual(len(extract_snapshot_signals(data)), 1)

    def test_legacy_malformed_source_ignored(self):
        source = {"ticker": "AAPL", "action": "BUY", "market": {
            "data_quality": "LIVE", "last_price": 100}}
        data = snapshot(source)
        data.pop("capital_allocation")
        data["opportunity_analysis"]["top_actionable"].append(None)
        self.assertEqual(len(extract_snapshot_signals(data)), 1)

    def test_legacy_nonfinite_price_rejected(self):
        source = {"ticker": "AAPL", "action": "BUY", "market": {
            "data_quality": "LIVE", "last_price": float("inf")}}
        data = snapshot(source)
        data.pop("capital_allocation")
        self.assertEqual(extract_snapshot_signals(data), [])

    def test_portfolio_nonfinite_price_rejected(self):
        data = snapshot()
        data["portfolio"] = [{"ticker": "AAPL", "portfolio_action": "ADD",
            "market": {"data_quality": "LIVE", "last_price": float("inf")}}]
        self.assertEqual(extract_snapshot_signals(data), [])

    def test_malformed_market_payload_rejected(self):
        source = {"ticker": "AAPL", "market": "not-a-market-dict"}
        self.assertEqual(extract_snapshot_signals(snapshot(source)), [])

    def test_nonfinite_live_market_helper_rejected(self):
        from engines.recommendation_performance_engine import live_market_item
        self.assertFalse(live_market_item({"market": {
            "data_quality": "LIVE", "last_price": float("inf")}}))
        self.assertFalse(live_market_item({"market": {
            "data_quality": "LIVE", "last_price": float("nan")}}))
        self.assertFalse(live_market_item(None))

    def test_allocated_entry_price_provenance_auditable(self):
        source = {"ticker": "AAPL", "market": {
            "data_quality": "LIVE", "last_price": 100}}
        record = extract_snapshot_signals(snapshot(source))[0]
        lineage = record["price_provenance"]
        self.assertEqual(lineage["allocation_price"], 100)
        self.assertEqual(lineage["verified_source_price"], 100)
        self.assertFalse(lineage["quote_freshness_verified"])

    def test_legacy_entry_provenance_remains_optional(self):
        source = {"ticker": "AAPL", "action": "BUY", "market": {
            "data_quality": "LIVE", "last_price": 100}}
        data = snapshot(source)
        data.pop("capital_allocation")
        record = extract_snapshot_signals(data)[0]
        self.assertIsNone(record["price_provenance"])

    def test_verified_source_accepted(self):
        source = {"ticker": "AAPL", "market": {
            "data_quality": "LIVE", "last_price": 100}}
        records = extract_snapshot_signals(snapshot(source))
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["ticker"], "AAPL")
        self.assertEqual(records[0]["source"], "NEW_ENTRY")


if __name__ == "__main__":
    unittest.main()
