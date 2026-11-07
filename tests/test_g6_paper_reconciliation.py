import unittest
from datetime import datetime, timezone, timedelta
from engines.g6_paper_reconciliation import reconcile_paper_snapshot


NOW = datetime(2026, 11, 7, 12, 0, tzinfo=timezone.utc)


def snapshot(**overrides):
    result = {
        "account_type": "PAPER",
        "verified": True,
        "complete": True,
        "timestamp": NOW.isoformat(),
        "orders": [{"client_order_id": "paper-1"}],
    }
    result.update(overrides)
    return result


class PaperReconciliationTests(unittest.TestCase):
    def test_matched_is_read_only_and_never_arms(self):
        result = reconcile_paper_snapshot(["paper-1"], snapshot(), now=NOW)
        self.assertFalse(result["ready"])
        self.assertEqual(result["matched"], ["paper-1"])
        self.assertEqual(result["reason"], "READ_ONLY_RECONCILIATION")

    def test_missing_local_order_remains_unresolved(self):
        result = reconcile_paper_snapshot(["paper-1", "paper-2"], snapshot(), now=NOW)
        self.assertEqual(result["unresolved"], ["paper-2"])
        self.assertFalse(result["ready"])

    def test_live_account_rejected(self):
        result = reconcile_paper_snapshot(["paper-1"], snapshot(account_type="LIVE"), now=NOW)
        self.assertEqual(result["reason"], "UNVERIFIED_PAPER_ACCOUNT")

    def test_unverified_or_partial_snapshot_rejected(self):
        for field in ("verified", "complete"):
            with self.subTest(field=field):
                result = reconcile_paper_snapshot(["paper-1"], snapshot(**{field: False}), now=NOW)
                self.assertFalse(result["ready"])

    def test_stale_and_future_snapshot_rejected(self):
        for delta in (-60, 5):
            with self.subTest(delta=delta):
                result = reconcile_paper_snapshot(
                    ["paper-1"], snapshot(timestamp=(NOW + timedelta(seconds=delta)).isoformat()), now=NOW
                )
                self.assertEqual(result["reason"], "STALE_OR_INVALID_SNAPSHOT")

    def test_duplicate_broker_ids_rejected(self):
        result = reconcile_paper_snapshot(
            ["paper-1"], snapshot(orders=[{"client_order_id": "paper-1"}] * 2), now=NOW
        )
        self.assertEqual(result["reason"], "DUPLICATE_BROKER_ORDER_IDS")


if __name__ == "__main__":
    unittest.main()
