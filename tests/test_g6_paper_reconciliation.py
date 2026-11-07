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

    def test_invalid_snapshot_age_limits_fail_closed(self):
        for limit in (None, "30", True, 0, -1, float("nan"), float("inf")):
            with self.subTest(limit=repr(limit)):
                result = reconcile_paper_snapshot(
                    ["paper-1"], snapshot(), now=NOW, max_age_seconds=limit
                )
                self.assertEqual(result["reason"], "INVALID_SNAPSHOT_AGE_LIMIT")
                self.assertFalse(result["ready"])

    def test_invalid_review_times_fail_closed(self):
        for invalid in ("", 0, False, datetime(2026, 11, 7, 12, 0)):
            with self.subTest(invalid=repr(invalid)):
                result = reconcile_paper_snapshot(
                    ["paper-1"], snapshot(), now=invalid
                )
                self.assertEqual(result["reason"], "STALE_OR_INVALID_SNAPSHOT")
                self.assertFalse(result["ready"])

    def test_expected_account_mismatch_blocks(self):
        result = reconcile_paper_snapshot(
            ["paper-1"], snapshot(account_id="DU12345"), now=NOW,
            expected_account_id="DU99999"
        )
        self.assertEqual(result["reason"], "BROKER_ACCOUNT_MISMATCH")

    def test_malformed_expected_account_blocks_direct_reconciliation(self):
        for account in ("U123", "DU", "DU123 ", "DU12X", "", 123):
            with self.subTest(account=repr(account)):
                result = reconcile_paper_snapshot(
                    ["paper-1"], snapshot(account_id=account), now=NOW,
                    expected_account_id=account
                )
                self.assertEqual(result["reason"], "BROKER_ACCOUNT_MISMATCH")
                self.assertFalse(result["ready"])

    def test_expected_account_match_is_still_read_only(self):
        result = reconcile_paper_snapshot(
            ["paper-1"], snapshot(account_id="DU12345"), now=NOW,
            expected_account_id="DU12345"
        )
        self.assertFalse(result["ready"])
        self.assertEqual(result["reason"], "READ_ONLY_RECONCILIATION")

    def test_invalid_broker_order_ids_rejected(self):
        for invalid in ("", " ", " paper-1 ", "x" * 129):
            with self.subTest(invalid=invalid):
                result = reconcile_paper_snapshot(
                    ["paper-1"],
                    snapshot(orders=[{"client_order_id": invalid}]),
                    now=NOW,
                )
                self.assertEqual(result["reason"], "INVALID_ORDER_LIST")
                self.assertFalse(result["ready"])

    def test_invalid_local_order_ids_rejected(self):
        for invalid in ("", " ", " paper-1 ", "x" * 129):
            with self.subTest(invalid=invalid):
                result = reconcile_paper_snapshot([invalid], snapshot(), now=NOW)
                self.assertEqual(result["reason"], "INVALID_LOCAL_ORDER_IDS")
                self.assertFalse(result["ready"])

    def test_duplicate_local_ids_rejected(self):
        result = reconcile_paper_snapshot(["paper-1", "paper-1"], snapshot(), now=NOW)
        self.assertEqual(result["reason"], "DUPLICATE_LOCAL_ORDER_IDS")

    def test_duplicate_broker_ids_rejected(self):
        result = reconcile_paper_snapshot(
            ["paper-1"], snapshot(orders=[{"client_order_id": "paper-1"}] * 2), now=NOW
        )
        self.assertEqual(result["reason"], "DUPLICATE_BROKER_ORDER_IDS")


if __name__ == "__main__":
    unittest.main()
