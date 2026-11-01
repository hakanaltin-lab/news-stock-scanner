"""Offline tests for G6.15 broker reconciliation; no broker calls."""

from datetime import datetime, timedelta, timezone
import tempfile
from pathlib import Path
import unittest

from engines.paper_authorization_reservation_ledger import (
    PaperAuthorizationReservationLedger,
)
from engines.paper_broker_reconciliation_state_machine import (
    reconcile_submission_attempt,
)
from engines.paper_submission_contract import CONTRACT_VERSION
import hashlib
import json


NOW = datetime(2026, 11, 1, 14, 0, tzinfo=timezone.utc)


def digest(payload):
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def contract():
    payload = {
        "version": CONTRACT_VERSION,
        "generated_at": NOW.isoformat(),
        "authorization_id": "11111111-1111-4111-8111-111111111111",
        "intent_sha256": "a" * 64,
        "shadow_order_sha256": "b" * 64,
        "idempotency_key": "paper-reconcile-0001",
    }
    return {
        "engine": "AURORA G6.13 Paper Submission Contract",
        "status": "SUBMISSION_CONTRACT_VALIDATED_NON_EXECUTABLE",
        "reason": "ARTIFACTS_BOUND_BUT_BROKER_PERMISSION_NOT_GRANTED",
        **payload,
        "contract_sha256": digest(payload),
        "authorization_id_must_be_atomically_consumed_before_submission": True,
        "next_gate": "PAPER_BROKER_ADAPTER_CODE_REVIEW_REQUIRED",
        "broker_submission_allowed": False,
        "paper_order_submission_allowed": False,
        "live_execution_allowed": False,
        "automatic_promotion_allowed": False,
        "real_money_trading_allowed": False,
        "broker_order_object_allowed": False,
    }


def reservation():
    directory = tempfile.TemporaryDirectory()
    ledger = PaperAuthorizationReservationLedger(
        Path(directory.name) / "reservation.sqlite3"
    )
    result = ledger.reserve(contract(), now=NOW)
    if result.get("status") != "AUTHORIZATION_RESERVED_NON_EXECUTABLE":
        directory.cleanup()
        raise AssertionError(result)
    result["_test_directory"] = directory
    return result


def attempt(reservation_result, dispatched=True, local_failure=False):
    return {
        "status": "SUBMISSION_ATTEMPT_RECORDED",
        "attempt_id": "22222222-2222-4222-8222-222222222222",
        "mode": "PAPER",
        "attempted_at": (NOW + timedelta(seconds=1)).isoformat(),
        "authorization_id": reservation_result["authorization_id"],
        "idempotency_key": reservation_result["idempotency_key"],
        "contract_sha256": reservation_result["contract_sha256"],
        "reservation_receipt_sha256": reservation_result[
            "reservation_receipt_sha256"
        ],
        "request_dispatched": dispatched,
        "local_failure_before_dispatch": local_failure,
        "expected_order": {
            "symbol": "NVDA",
            "side": "BUY",
            "quantity": 2,
            "limit_price": 100.0,
        },
        "client_id": 82 if dispatched else None,
        "order_id": 1001 if dispatched else None,
        "paper_account_evidence_token": "IBKR-EVID-ABCDEF1234567890",
        "automatic_retry_allowed": False,
        "live_execution_allowed": False,
    }


def observation(
    status="Submitted",
    filled=0,
    remaining=2,
    observed=True,
    generated_at=None,
):
    return {
        "status": "BROKER_OBSERVATION_READ_ONLY",
        "mode": "PAPER",
        "broker_read_only": True,
        "live_trading_allowed": False,
        "order_submission_hard_blocked": True,
        "snapshot_verified": True,
        "snapshot_generated_at_utc": (
            generated_at or (NOW + timedelta(seconds=2))
        ).isoformat(),
        "paper_account_evidence_token": "IBKR-EVID-ABCDEF1234567890",
        "order_observed": observed,
        "order": (
            {
                "perm_id": 900001,
                "client_id": 82,
                "order_id": 1001,
                "symbol": "NVDA",
                "side": "BUY",
                "total_quantity": 2,
                "limit_price": 100.0,
                "broker_status": status,
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


class ReconciliationStateMachineTests(unittest.TestCase):
    def setUp(self):
        self.reservation = reservation()

    def tearDown(self):
        self.reservation["_test_directory"].cleanup()
        self.reservation.pop("_test_directory", None)

    def evaluate(self, submission_attempt=None, broker_observation=None, now=None):
        clean_reservation = {
            key: value
            for key, value in self.reservation.items()
            if key != "_test_directory"
        }
        return reconcile_submission_attempt(
            clean_reservation,
            attempt=(
                attempt(clean_reservation)
                if submission_attempt is None
                else submission_attempt
            ),
            broker_observation=broker_observation,
            now=now or (NOW + timedelta(seconds=3)),
        )

    def assert_never_retry(self, result):
        self.assertFalse(result["automatic_retry_allowed"])
        self.assertFalse(result["same_authorization_retry_allowed"])
        self.assertFalse(result["paper_order_submission_allowed"])
        self.assertFalse(result["live_execution_allowed"])
        self.assertFalse(result["automatic_cancel_allowed"])
        self.assertFalse(result["automatic_modify_allowed"])

    def test_reserved_without_attempt_is_not_retried(self):
        clean = {
            k: v for k, v in self.reservation.items()
            if k != "_test_directory"
        }
        result = reconcile_submission_attempt(
            clean,
            attempt=None,
            broker_observation=None,
            now=NOW + timedelta(seconds=3),
        )
        self.assertEqual(result["status"], "RESERVED_NO_SUBMISSION_ATTEMPT")
        self.assertFalse(result["manual_reconciliation_required"])
        self.assert_never_retry(result)

    def test_local_failure_before_dispatch_requires_new_human_authorization(self):
        clean = {
            k: v for k, v in self.reservation.items()
            if k != "_test_directory"
        }
        local = attempt(clean, dispatched=False, local_failure=True)
        result = self.evaluate(submission_attempt=local)
        self.assertEqual(result["status"], "LOCAL_FAILURE_BEFORE_BROKER_DISPATCH")
        self.assertEqual(
            result["next_action"],
            "NEW_HUMAN_AUTHORIZATION_REQUIRED_FOR_ANY_RETRY",
        )
        self.assert_never_retry(result)

    def test_dispatched_without_observation_is_unknown_do_not_retry(self):
        result = self.evaluate(broker_observation=None)
        self.assertEqual(result["status"], "BROKER_OUTCOME_UNKNOWN_DO_NOT_RETRY")
        self.assertTrue(result["manual_reconciliation_required"])
        self.assert_never_retry(result)

    def test_complete_readonly_snapshot_with_no_matching_order_is_still_unknown(self):
        result = self.evaluate(
            broker_observation=observation(observed=False)
        )
        self.assertEqual(result["status"], "BROKER_OUTCOME_UNKNOWN_DO_NOT_RETRY")
        self.assert_never_retry(result)

    def test_pending_submit_is_not_assumed_rejected(self):
        result = self.evaluate(
            broker_observation=observation(
                status="PendingSubmit", filled=0, remaining=2
            )
        )
        self.assertEqual(result["status"], "BROKER_SUBMISSION_PENDING")
        self.assert_never_retry(result)

    def test_submitted_open_order(self):
        result = self.evaluate(
            broker_observation=observation(
                status="Submitted", filled=0, remaining=2
            )
        )
        self.assertEqual(result["status"], "BROKER_ORDER_OPEN_WORKING")
        self.assertFalse(result["terminal_broker_state_observed"])
        self.assert_never_retry(result)

    def test_presubmitted_is_active(self):
        result = self.evaluate(
            broker_observation=observation(
                status="PreSubmitted", filled=0, remaining=2
            )
        )
        self.assertEqual(result["status"], "BROKER_ORDER_OPEN_WORKING")
        self.assert_never_retry(result)

    def test_partial_fill_remains_non_retryable(self):
        result = self.evaluate(
            broker_observation=observation(
                status="Submitted", filled=1, remaining=1
            )
        )
        self.assertEqual(
            result["status"],
            "BROKER_ORDER_PARTIALLY_FILLED_WORKING",
        )
        self.assert_never_retry(result)

    def test_filled_requires_quantity_consistency(self):
        result = self.evaluate(
            broker_observation=observation(
                status="Filled", filled=2, remaining=0
            )
        )
        self.assertEqual(result["status"], "BROKER_ORDER_FILLED")
        self.assertTrue(result["terminal_broker_state_observed"])
        self.assertEqual(result["next_action"], "NO_RETRY_FINALIZE_AUDIT")
        self.assert_never_retry(result)

        conflict = self.evaluate(
            broker_observation=observation(
                status="Filled", filled=1, remaining=1
            )
        )
        self.assertEqual(conflict["status"], "BLOCKED")
        self.assertEqual(conflict["reason"], "CONFLICTING_FILLED_QUANTITIES")
        self.assert_never_retry(conflict)

    def test_cancel_pending_is_not_final_and_never_retried(self):
        for status in ("PendingCancel", "PreCancelled"):
            with self.subTest(status=status):
                result = self.evaluate(
                    broker_observation=observation(
                        status=status, filled=0, remaining=2
                    )
                )
                self.assertEqual(result["status"], "BROKER_CANCEL_PENDING")
                self.assertFalse(result["terminal_broker_state_observed"])
                self.assert_never_retry(result)

    def test_cancelled_unfilled_and_partial(self):
        unfilled = self.evaluate(
            broker_observation=observation(
                status="Cancelled", filled=0, remaining=0
            )
        )
        self.assertEqual(
            unfilled["status"], "BROKER_ORDER_CANCELLED_UNFILLED"
        )
        self.assertTrue(unfilled["terminal_broker_state_observed"])
        self.assert_never_retry(unfilled)

        partial = self.evaluate(
            broker_observation=observation(
                status="Cancelled", filled=1, remaining=0
            )
        )
        self.assertEqual(
            partial["status"],
            "BROKER_ORDER_PARTIALLY_FILLED_CANCELLED",
        )
        self.assertTrue(partial["terminal_broker_state_observed"])
        self.assert_never_retry(partial)

    def test_inactive_and_warnstate_require_manual_review(self):
        inactive = self.evaluate(
            broker_observation=observation(
                status="Inactive", filled=0, remaining=2
            )
        )
        self.assertEqual(
            inactive["status"],
            "BROKER_ORDER_INACTIVE_MANUAL_REVIEW",
        )
        self.assert_never_retry(inactive)

        warning = self.evaluate(
            broker_observation=observation(
                status="WarnState", filled=0, remaining=2
            )
        )
        self.assertEqual(
            warning["status"],
            "BROKER_WARNING_MANUAL_REVIEW",
        )
        self.assert_never_retry(warning)

    def test_unknown_status_is_not_guessed(self):
        result = self.evaluate(
            broker_observation=observation(
                status="FutureNewStatus", filled=0, remaining=2
            )
        )
        self.assertEqual(
            result["status"],
            "BROKER_STATUS_UNKNOWN_MANUAL_REVIEW",
        )
        self.assertEqual(result["reason"], "UNSUPPORTED_BROKER_STATUS")
        self.assert_never_retry(result)

    def test_identity_or_order_mismatch_blocks(self):
        mismatches = [
            ("client_id", 999),
            ("order_id", 999),
            ("symbol", "AMD"),
            ("side", "SELL"),
            ("total_quantity", 3),
            ("limit_price", 101.0),
        ]
        for field, value in mismatches:
            with self.subTest(field=field):
                obs = observation()
                obs["order"][field] = value
                result = self.evaluate(broker_observation=obs)
                self.assertEqual(
                    result["reason"],
                    "INVALID_OR_STALE_BROKER_OBSERVATION",
                )
                self.assert_never_retry(result)

    def test_stale_or_unsafe_observation_blocks(self):
        stale = observation(
            generated_at=NOW - timedelta(seconds=61)
        )
        result = self.evaluate(
            broker_observation=stale,
            now=NOW + timedelta(seconds=3),
        )
        self.assertEqual(
            result["reason"],
            "INVALID_OR_STALE_BROKER_OBSERVATION",
        )

        unsafe = observation()
        unsafe["live_trading_allowed"] = True
        result = self.evaluate(broker_observation=unsafe)
        self.assertEqual(
            result["reason"],
            "INVALID_OR_STALE_BROKER_OBSERVATION",
        )

    def test_local_pre_dispatch_failure_conflicts_with_broker_evidence(self):
        clean = {
            k: v for k, v in self.reservation.items()
            if k != "_test_directory"
        }
        local = attempt(clean, dispatched=False, local_failure=True)
        result = self.evaluate(
            submission_attempt=local,
            broker_observation=observation(),
        )
        self.assertEqual(
            result["reason"],
            "BROKER_OBSERVATION_CONFLICTS_WITH_LOCAL_PRE_DISPATCH_FAILURE",
        )
        self.assert_never_retry(result)

    def test_attempt_must_follow_reservation_and_not_be_future_dated(self):
        clean = {
            k: v for k, v in self.reservation.items()
            if k != "_test_directory"
        }
        before = attempt(clean)
        before["attempted_at"] = (NOW - timedelta(seconds=1)).isoformat()
        result = reconcile_submission_attempt(
            clean,
            attempt=before,
            broker_observation=None,
            now=NOW + timedelta(seconds=3),
        )
        self.assertEqual(result["reason"], "ATTEMPT_PREDATES_RESERVATION")
        self.assert_never_retry(result)

        future = attempt(clean)
        future["attempted_at"] = (NOW + timedelta(seconds=10)).isoformat()
        result = reconcile_submission_attempt(
            clean,
            attempt=future,
            broker_observation=None,
            now=NOW + timedelta(seconds=3),
        )
        self.assertEqual(result["reason"], "ATTEMPT_TIMESTAMP_IN_FUTURE")
        self.assert_never_retry(result)

    def test_broker_observation_must_follow_attempt(self):
        obs = observation(
            generated_at=NOW,
        )
        result = self.evaluate(
            broker_observation=obs,
            now=NOW + timedelta(seconds=3),
        )
        self.assertEqual(
            result["reason"],
            "BROKER_OBSERVATION_PREDATES_ATTEMPT",
        )
        self.assert_never_retry(result)

    def test_account_evidence_token_must_match_attempt(self):
        obs = observation()
        obs["paper_account_evidence_token"] = "IBKR-EVID-1234567890ABCDEF"
        result = self.evaluate(broker_observation=obs)
        self.assertEqual(
            result["reason"],
            "INVALID_OR_STALE_BROKER_OBSERVATION",
        )
        self.assert_never_retry(result)

    def test_active_quantity_contradiction_blocks(self):
        obs = observation(
            status="Submitted",
            filled=1,
            remaining=0,
        )
        result = self.evaluate(broker_observation=obs)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["reason"], "CONFLICTING_ACTIVE_QUANTITIES")
        self.assert_never_retry(result)

    def test_cancelled_with_remaining_quantity_blocks(self):
        obs = observation(
            status="Cancelled",
            filled=0,
            remaining=2,
        )
        result = self.evaluate(broker_observation=obs)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(
            result["reason"],
            "CONFLICTING_CANCELLED_QUANTITIES",
        )
        self.assert_never_retry(result)

    def test_invalid_evaluation_time_fails_closed(self):
        clean = {
            k: v for k, v in self.reservation.items()
            if k != "_test_directory"
        }
        result = reconcile_submission_attempt(
            clean,
            attempt=attempt(clean),
            broker_observation=observation(),
            now="not-a-time",
        )
        self.assertEqual(result["reason"], "INVALID_EVALUATION_TIME")
        self.assert_never_retry(result)


if __name__ == "__main__":
    unittest.main()
