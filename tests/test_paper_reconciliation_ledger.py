"""Offline tests for G6.16 persistent reconciliation ledger."""

from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import stat
import tempfile
import unittest

from engines.paper_reconciliation_ledger import PaperReconciliationLedger


NOW = datetime(2026, 11, 1, 15, 0, tzinfo=timezone.utc)


def reservation(
    authorization_id="11111111-1111-4111-8111-111111111111",
    idempotency_key="paper-ledger-0001",
):
    return {
        "status": "AUTHORIZATION_RESERVED_NON_EXECUTABLE",
        "reason": "AT_MOST_ONCE_RESERVATION_RECORDED",
        "reserved": True,
        "reservation_state": "RESERVED_NON_EXECUTABLE",
        "authorization_id": authorization_id,
        "idempotency_key": idempotency_key,
        "contract_sha256": "a" * 64,
        "reservation_receipt_sha256": "b" * 64,
        "reserved_at": NOW.isoformat(),
        "paper_order_submission_allowed": False,
        "live_execution_allowed": False,
        "broker_order_object_allowed": False,
    }


def attempt(reservation_result, attempt_id="22222222-2222-4222-8222-222222222222"):
    return {
        "status": "SUBMISSION_ATTEMPT_RECORDED",
        "attempt_id": attempt_id,
        "mode": "PAPER",
        "attempted_at": (NOW + timedelta(seconds=1)).isoformat(),
        "authorization_id": reservation_result["authorization_id"],
        "idempotency_key": reservation_result["idempotency_key"],
        "contract_sha256": reservation_result["contract_sha256"],
        "reservation_receipt_sha256": reservation_result[
            "reservation_receipt_sha256"
        ],
        "request_dispatched": True,
        "local_failure_before_dispatch": False,
        "expected_order": {
            "symbol": "NVDA",
            "side": "BUY",
            "quantity": 2,
            "limit_price": 100.0,
        },
        "client_id": 82,
        "order_id": 1001,
        "paper_account_evidence_token": "IBKR-EVID-ABCDEF1234567890",
        "automatic_retry_allowed": False,
        "live_execution_allowed": False,
    }


def observation(
    broker_status="Submitted",
    filled=0,
    remaining=2,
    seconds=2,
    perm_id=900001,
    client_id=82,
    order_id=1001,
    observed=True,
):
    return {
        "status": "BROKER_OBSERVATION_READ_ONLY",
        "mode": "PAPER",
        "broker_read_only": True,
        "live_trading_allowed": False,
        "order_submission_hard_blocked": True,
        "snapshot_verified": True,
        "snapshot_generated_at_utc": (
            NOW + timedelta(seconds=seconds)
        ).isoformat(),
        "paper_account_evidence_token": "IBKR-EVID-ABCDEF1234567890",
        "order_observed": observed,
        "order": (
            {
                "perm_id": perm_id,
                "client_id": client_id,
                "order_id": order_id,
                "symbol": "NVDA",
                "side": "BUY",
                "total_quantity": 2,
                "limit_price": 100.0,
                "broker_status": broker_status,
                "filled_quantity": filled,
                "remaining_quantity": remaining,
                "execution_ids": (
                    []
                    if filled == 0
                    else [f"exec-{index}" for index in range(1, int(filled) + 1)]
                ),
            }
            if observed
            else None
        ),
    }


class ReconciliationLedgerTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name) / "reconciliation.sqlite3"
        self.ledger = PaperReconciliationLedger(self.path)
        self.res = reservation()
        self.att = attempt(self.res)

    def tearDown(self):
        self.directory.cleanup()

    def record(self, obs=None, seconds=3):
        return self.ledger.record(
            self.res,
            self.att,
            broker_observation=obs,
            now=NOW + timedelta(seconds=seconds),
        )

    def assert_safe(self, result):
        self.assertFalse(result["automatic_retry_allowed"])
        self.assertFalse(result["same_authorization_retry_allowed"])
        self.assertFalse(result["paper_order_submission_allowed"])
        self.assertFalse(result["live_execution_allowed"])
        self.assertFalse(result["automatic_cancel_allowed"])
        self.assertFalse(result["automatic_modify_allowed"])

    def test_unknown_then_open_transition_is_persisted(self):
        first = self.record(obs=None, seconds=2)
        self.assertEqual(
            first["reconciliation_state"],
            "BROKER_OUTCOME_UNKNOWN_DO_NOT_RETRY",
        )
        second = self.record(
            obs=observation("Submitted", 0, 2, seconds=3),
            seconds=4,
        )
        self.assertEqual(
            second["reconciliation_state"],
            "BROKER_ORDER_OPEN_WORKING",
        )
        self.assertTrue(first["ledger_recorded"])
        self.assertTrue(second["ledger_recorded"])
        self.assert_safe(second)
        self.assertEqual(stat.S_IMODE(os.stat(self.path).st_mode), 0o600)

    def test_monotonic_partial_cancel_flow(self):
        open_state = self.record(
            obs=observation("Submitted", 0, 2, seconds=2),
            seconds=3,
        )
        partial = self.record(
            obs=observation("Submitted", 1, 1, seconds=4),
            seconds=5,
        )
        pending_cancel = self.record(
            obs=observation("PendingCancel", 1, 1, seconds=6),
            seconds=7,
        )
        cancelled = self.record(
            obs=observation("Cancelled", 1, 0, seconds=8),
            seconds=9,
        )
        self.assertEqual(
            [open_state["reconciliation_state"],
             partial["reconciliation_state"],
             pending_cancel["reconciliation_state"],
             cancelled["reconciliation_state"]],
            [
                "BROKER_ORDER_OPEN_WORKING",
                "BROKER_ORDER_PARTIALLY_FILLED_WORKING",
                "BROKER_CANCEL_PENDING",
                "BROKER_ORDER_PARTIALLY_FILLED_CANCELLED",
            ],
        )
        self.assertTrue(cancelled["terminal_state"])
        self.assert_safe(cancelled)

    def test_terminal_fill_cannot_regress(self):
        filled = self.record(
            obs=observation("Filled", 2, 0, seconds=2),
            seconds=3,
        )
        self.assertEqual(filled["reconciliation_state"], "BROKER_ORDER_FILLED")

        later_open = self.record(
            obs=observation("Submitted", 0, 2, seconds=4),
            seconds=5,
        )
        self.assertEqual(later_open["status"], "TERMINAL_STATE_IMMUTABLE")
        self.assertEqual(
            later_open["reason"],
            "TERMINAL_RECONCILIATION_ALREADY_RECORDED",
        )
        self.assert_safe(later_open)

    def test_cancelled_terminal_cannot_regress(self):
        cancelled = self.record(
            obs=observation("Cancelled", 0, 0, seconds=2),
            seconds=3,
        )
        self.assertEqual(
            cancelled["reconciliation_state"],
            "BROKER_ORDER_CANCELLED_UNFILLED",
        )
        later = self.record(
            obs=observation("Submitted", 0, 2, seconds=4),
            seconds=5,
        )
        self.assertEqual(later["status"], "TERMINAL_STATE_IMMUTABLE")
        self.assert_safe(later)

    def test_stale_snapshot_cannot_overwrite_newer_state(self):
        newer = self.record(
            obs=observation("Submitted", 1, 1, seconds=6),
            seconds=7,
        )
        self.assertEqual(
            newer["reconciliation_state"],
            "BROKER_ORDER_PARTIALLY_FILLED_WORKING",
        )
        stale = self.record(
            obs=observation("Submitted", 0, 2, seconds=4),
            seconds=8,
        )
        self.assertEqual(stale["status"], "BLOCKED")
        self.assertEqual(stale["reason"], "STALE_STATE_REGRESSION_BLOCKED")
        self.assert_safe(stale)

    def test_broker_perm_identity_cannot_change_after_observation(self):
        first = self.record(
            obs=observation("Submitted", 0, 2, seconds=2, perm_id=900001),
            seconds=3,
        )
        self.assertTrue(first["ledger_recorded"])
        changed = self.record(
            obs=observation("Submitted", 0, 2, seconds=4, perm_id=900002),
            seconds=5,
        )
        self.assertEqual(changed["status"], "BLOCKED")
        self.assertEqual(
            changed["reason"],
            "BROKER_IDENTITY_REGRESSION_BLOCKED",
        )
        self.assertEqual(changed["field"], "perm_id")
        self.assert_safe(changed)

    def test_fill_quantity_cannot_decrease(self):
        partial = self.record(
            obs=observation("Submitted", 1, 1, seconds=2),
            seconds=3,
        )
        self.assertTrue(partial["ledger_recorded"])
        regressed = self.record(
            obs=observation("PendingCancel", 0, 2, seconds=4),
            seconds=5,
        )
        self.assertEqual(regressed["status"], "BLOCKED")
        self.assertEqual(
            regressed["reason"],
            "FILLED_QUANTITY_REGRESSION_BLOCKED",
        )
        self.assert_safe(regressed)

    def test_invalid_state_transition_is_blocked(self):
        partial = self.record(
            obs=observation("Submitted", 1, 1, seconds=2),
            seconds=3,
        )
        self.assertTrue(partial["ledger_recorded"])
        pending_submit = self.record(
            obs=observation("PendingSubmit", 0, 2, seconds=4),
            seconds=5,
        )
        self.assertEqual(pending_submit["status"], "BLOCKED")
        self.assertEqual(
            pending_submit["reason"],
            "INVALID_STATE_TRANSITION",
        )
        self.assert_safe(pending_submit)

    def test_same_attempt_id_cannot_change_authorization_identity(self):
        first = self.record(
            obs=observation("Submitted", 0, 2, seconds=2),
            seconds=3,
        )
        self.assertTrue(first["ledger_recorded"])

        changed_res = reservation(
            authorization_id="33333333-3333-4333-8333-333333333333",
            idempotency_key="paper-ledger-9999",
        )
        changed_att = attempt(
            changed_res,
            attempt_id=self.att["attempt_id"],
        )
        result = self.ledger.record(
            changed_res,
            changed_att,
            broker_observation=observation(
                "Submitted", 0, 2, seconds=4
            ),
            now=NOW + timedelta(seconds=5),
        )
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["reason"], "ATTEMPT_IDENTITY_CHANGED")
        self.assert_safe(result)

    def test_exact_duplicate_event_is_idempotent(self):
        obs = observation("Submitted", 0, 2, seconds=2)
        first = self.record(obs=obs, seconds=3)
        second = self.record(obs=obs, seconds=3)
        self.assertTrue(first["ledger_recorded"])
        self.assertEqual(
            second["status"],
            "RECONCILIATION_EVENT_ALREADY_RECORDED",
        )
        self.assertTrue(second["duplicate"])
        self.assertFalse(second["ledger_recorded"])
        self.assert_safe(second)

    def test_local_pre_dispatch_failure_is_terminal_for_same_attempt(self):
        local = dict(self.att)
        local["request_dispatched"] = False
        local["local_failure_before_dispatch"] = True
        first = self.ledger.record(
            self.res,
            local,
            broker_observation=None,
            now=NOW + timedelta(seconds=2),
        )
        self.assertEqual(
            first["reconciliation_state"],
            "LOCAL_FAILURE_BEFORE_BROKER_DISPATCH",
        )
        second = self.ledger.record(
            self.res,
            local,
            broker_observation=None,
            now=NOW + timedelta(seconds=3),
        )
        self.assertEqual(
            second["status"],
            "RECONCILIATION_EVENT_ALREADY_RECORDED",
        )
        self.assert_safe(second)

    def test_upstream_blocked_evidence_is_not_persisted(self):
        stale = observation("Submitted", 0, 2, seconds=-70)
        result = self.record(
            obs=stale,
            seconds=3,
        )
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(
            result["reason"],
            "G6_15_RECONCILIATION_BLOCKED",
        )
        self.assertFalse(self.path.exists())
        self.assert_safe(result)

    def test_ledger_unavailable_fails_closed(self):
        parent_file = Path(self.directory.name) / "not-a-directory"
        parent_file.write_text("x", encoding="utf-8")
        ledger = PaperReconciliationLedger(
            parent_file / "ledger.sqlite3"
        )
        result = ledger.record(
            self.res,
            self.att,
            broker_observation=observation(
                "Submitted", 0, 2, seconds=2
            ),
            now=NOW + timedelta(seconds=3),
        )
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(
            result["reason"],
            "RECONCILIATION_LEDGER_UNAVAILABLE",
        )
        self.assert_safe(result)


if __name__ == "__main__":
    unittest.main()
