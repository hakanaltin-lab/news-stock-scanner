import unittest
from datetime import datetime, timezone
from engines.g6_ibkr_paper_snapshot_adapter import normalize_ibkr_paper_orders
from engines.g6_paper_reconciliation import reconcile_paper_snapshot

NOW = datetime(2026, 11, 7, 12, 0, tzinfo=timezone.utc)
ORDERS = [{"orderRef": "aurora-1", "account": "DU12345"}]


class IBKRSnapshotAdapterTests(unittest.TestCase):
    def test_unverified_transport_fails_closed(self):
        result = normalize_ibkr_paper_orders(
            ORDERS, account_id="DU12345", captured_at=NOW, complete=True
        )
        self.assertFalse(result["verified"])

    def test_partial_snapshot_fails_closed(self):
        result = normalize_ibkr_paper_orders(
            ORDERS, account_id="DU12345", captured_at=NOW,
            transport_authenticated=True
        )
        self.assertFalse(result["complete"])

    def test_live_account_rejected(self):
        result = normalize_ibkr_paper_orders(
            ORDERS, account_id="U12345", captured_at=NOW,
            transport_authenticated=True, complete=True
        )
        self.assertFalse(result["verified"])

    def test_order_account_mismatch_rejected(self):
        result = normalize_ibkr_paper_orders(
            ORDERS, account_id="DU99999", captured_at=NOW,
            transport_authenticated=True, complete=True
        )
        self.assertEqual(result["reason"], "ORDER_ACCOUNT_MISMATCH")

    def test_missing_order_reference_rejected(self):
        result = normalize_ibkr_paper_orders(
            [{"account": "DU12345"}], account_id="DU12345", captured_at=NOW,
            transport_authenticated=True, complete=True
        )
        self.assertEqual(result["reason"], "MISSING_ORDER_REFERENCE")

    def test_missing_capture_timestamp_fails_closed(self):
        result = normalize_ibkr_paper_orders(
            ORDERS, account_id="DU12345",
            transport_authenticated=True, complete=True
        )
        self.assertEqual(result["reason"], "INVALID_CAPTURE_TIMESTAMP")
        self.assertFalse(result["verified"])

    def test_naive_capture_timestamp_fails_closed(self):
        result = normalize_ibkr_paper_orders(
            ORDERS, account_id="DU12345",
            captured_at=datetime(2026, 11, 7, 12, 0),
            transport_authenticated=True, complete=True
        )
        self.assertEqual(result["reason"], "INVALID_CAPTURE_TIMESTAMP")

    def test_duplicate_order_references_fail_closed(self):
        result = normalize_ibkr_paper_orders(
            ORDERS + ORDERS, account_id="DU12345", captured_at=NOW,
            transport_authenticated=True, complete=True
        )
        self.assertEqual(result["reason"], "DUPLICATE_BROKER_ORDER_REFERENCE")
        self.assertFalse(result["verified"])
        self.assertEqual(result["orders"], [])

    def test_order_reference_whitespace_fails_closed(self):
        result = normalize_ibkr_paper_orders(
            [{"orderRef": " aurora-1 ", "account": "DU12345"}],
            account_id="DU12345", captured_at=NOW,
            transport_authenticated=True, complete=True
        )
        self.assertEqual(result["reason"], "INVALID_ORDER_REFERENCE_WHITESPACE")
        self.assertFalse(result["verified"])

    def test_normalized_snapshot_remains_read_only(self):
        snapshot = normalize_ibkr_paper_orders(
            ORDERS, account_id="DU12345", captured_at=NOW,
            transport_authenticated=True, complete=True
        )
        result = reconcile_paper_snapshot(
            ["aurora-1"], snapshot, expected_account_id="DU12345", now=NOW
        )
        self.assertEqual(result["matched"], ["aurora-1"])
        self.assertFalse(result["ready"])


if __name__ == "__main__":
    unittest.main()
