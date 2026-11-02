"""Additional fail-closed regression scenarios for G6.11 read-only correlation.

No broker connection or order submission occurs in this test module.
"""
import copy
import unittest

from engines.ibkr_snapshot_correlation_bridge import diagnose_snapshot


def safe_snapshot():
    return {
        "status": "CONNECTED",
        "requests_complete": {k: True for k in (
            "managed_accounts", "account_summary", "positions", "open_orders", "executions"
        )},
        "open_orders": [{
            "perm_id": 123, "order_id": 1, "client_id": 82,
            "account": "PAPER-REDACTED"
        }],
        "order_status": [{
            "perm_id": 123, "order_id": 1, "client_id": 82,
            "filled": 0, "remaining": 1, "status": "Submitted"
        }],
        "executions": [],
        "order_submission_hard_blocked": True,
        "live_trading_allowed": False,
        "config": {"mode": "PAPER", "endpoint_safe": True, "read_only": True},
        "paper_account_guard": {
            "paper_account_verified": True,
            "verified_account_fingerprints": ["PAPER-REDACTED"]
        },
    }


def local_and_mapping():
    return (
        {"k": {"account": "PAPER-REDACTED", "idempotency_key": "k"}},
        {"k": {
            "account": "PAPER-REDACTED", "perm_id": 123,
            "order_id": 1, "client_id": 82
        }},
    )


class TestReviewRegressions(unittest.TestCase):
    def check_blocked(self, snapshot, local=None, mapping=None):
        if local is None or mapping is None:
            local, mapping = local_and_mapping()
        result = diagnose_snapshot(snapshot, local, mapping)
        self.assertEqual(result["status"], "BLOCKED", result)
        self.assertIs(result["paper_order_submission_allowed"], False)
        self.assertIs(result["live_trading_allowed"], False)
        return result

    def test_known_good_snapshot_is_diagnostic_only(self):
        local, mapping = local_and_mapping()
        result = diagnose_snapshot(safe_snapshot(), local, mapping)
        self.assertEqual(result["status"], "CORRELATIONS_VERIFIED")
        self.assertIs(result["paper_order_submission_allowed"], False)
        self.assertIs(result["live_trading_allowed"], False)

    def test_disconnected_session_never_uses_stale_order_rows(self):
        snapshot = safe_snapshot()
        snapshot["status"] = "DISCONNECTED"
        self.assertEqual(
            self.check_blocked(snapshot)["reason"], "SNAPSHOT_NOT_CONNECTED"
        )

    def test_reconnect_with_changed_permanent_id_blocks(self):
        snapshot = safe_snapshot()
        snapshot["open_orders"][0]["perm_id"] = 999
        snapshot["order_status"][0]["perm_id"] = 999
        self.assertEqual(
            self.check_blocked(snapshot)["reason"],
            "BROKER_CORRELATION_NOT_OBSERVED",
        )

    def test_conflicting_status_with_valid_account_evidence_blocks(self):
        snapshot = safe_snapshot()
        snapshot["order_status"].append({
            "perm_id": 123, "order_id": 1, "client_id": 999,
            "filled": 0, "remaining": 1, "status": "Submitted"
        })
        self.assertEqual(
            self.check_blocked(snapshot)["reason"],
            "CONFLICTING_ORDER_STATUS_IDENTITY",
        )

    def test_invalid_remaining_with_valid_account_evidence_blocks(self):
        for invalid in (-1, float("nan"), float("inf"), None):
            with self.subTest(remaining=str(invalid)):
                snapshot = safe_snapshot()
                snapshot["order_status"][0]["remaining"] = invalid
                self.assertEqual(
                    self.check_blocked(snapshot)["reason"],
                    "INVALID_REMAINING_QUANTITY",
                )

    def test_empty_mapping_cannot_be_misread_as_order_verified(self):
        snapshot = safe_snapshot()
        snapshot["open_orders"] = []
        snapshot["order_status"] = []
        self.assertEqual(
            self.check_blocked(snapshot, {}, {})["reason"],
            "MISSING_MAPPING",
        )

    def test_missing_client_id_blocks_even_with_matching_permanent_id(self):
        snapshot = safe_snapshot()
        del snapshot["open_orders"][0]["client_id"]
        self.assertEqual(
            self.check_blocked(snapshot)["reason"],
            "INVALID_OPEN_ORDER_IDENTITY",
        )


if __name__ == "__main__":
    unittest.main()
