"""Offline tests for G6.17 trusted submission-attempt journal."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import stat
import tempfile
import unittest

from engines.paper_authorization_reservation_ledger import (
    PaperAuthorizationReservationLedger,
)
from engines.paper_broker_reconciliation_state_machine import (
    reconcile_submission_attempt,
)
from engines.paper_submission_attempt_journal import (
    PaperSubmissionAttemptJournal,
)
from engines.paper_submission_contract import CONTRACT_VERSION


NOW = datetime(2026, 11, 1, 16, 0, tzinfo=timezone.utc)
ATTEMPT_ID = "22222222-2222-4222-8222-222222222222"
AUTH_ID = "11111111-1111-4111-8111-111111111111"
TOKEN = "IBKR-EVID-ABCDEF1234567890"


def digest(payload):
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def intent(key="paper-attempt-0001"):
    return {
        "symbol": "NVDA",
        "side": "BUY",
        "order_type": "LMT",
        "quantity": 2,
        "limit_price": 100.0,
        "idempotency_key": key,
    }


def contract(order_intent=None, generated_at=None):
    order_intent = order_intent or intent()
    normalized = {
        "symbol": order_intent["symbol"],
        "side": order_intent["side"],
        "order_type": order_intent["order_type"],
        "quantity": order_intent["quantity"],
        "limit_price": float(order_intent["limit_price"]),
        "idempotency_key": order_intent["idempotency_key"],
    }
    payload = {
        "version": CONTRACT_VERSION,
        "generated_at": (
            generated_at or (NOW - timedelta(seconds=5))
        ).isoformat(),
        "authorization_id": AUTH_ID,
        "intent_sha256": digest(normalized),
        "shadow_order_sha256": "b" * 64,
        "idempotency_key": order_intent["idempotency_key"],
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


class SubmissionAttemptJournalTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.reservation_path = (
            Path(self.directory.name) / "reservation.sqlite3"
        )
        self.attempt_path = (
            Path(self.directory.name) / "attempt.sqlite3"
        )
        self.order_intent = intent()
        self.contract = contract(self.order_intent)
        self.reservation = PaperAuthorizationReservationLedger(
            self.reservation_path
        ).reserve(
            self.contract,
            now=NOW,
        )
        if self.reservation.get("status") != "AUTHORIZATION_RESERVED_NON_EXECUTABLE":
            raise AssertionError(self.reservation)
        self.journal = PaperSubmissionAttemptJournal(
            self.attempt_path,
            self.reservation_path,
        )

    def tearDown(self):
        self.directory.cleanup()

    def prepare(self, now=None, attempt_id=ATTEMPT_ID):
        return self.journal.prepare(
            self.reservation,
            self.contract,
            self.order_intent,
            TOKEN,
            now=now or (NOW + timedelta(seconds=5)),
            attempt_id=attempt_id,
        )

    def assert_safe(self, result):
        self.assertFalse(result["broker_submission_allowed"])
        self.assertFalse(result["paper_order_submission_allowed"])
        self.assertFalse(result["live_execution_allowed"])
        self.assertFalse(result["automatic_retry_allowed"])
        self.assertFalse(result["same_authorization_retry_allowed"])
        self.assertFalse(result["automatic_cancel_allowed"])
        self.assertFalse(result["automatic_modify_allowed"])
        self.assertFalse(result["broker_order_object_allowed"])

    def test_prepare_is_persisted_but_not_a_dispatch_artifact(self):
        result = self.prepare()
        self.assertEqual(
            result["status"],
            "ATTEMPT_PREPARED_NON_EXECUTABLE",
        )
        self.assertFalse(result["attempt_artifact_available"])
        self.assertEqual(result["attempt_id"], ATTEMPT_ID)
        self.assertEqual(stat.S_IMODE(os.stat(self.attempt_path).st_mode), 0o600)
        self.assert_safe(result)

        readback = self.journal.get_attempt_artifact(ATTEMPT_ID)
        self.assertEqual(
            readback["status"],
            "ATTEMPT_PREPARED_NON_EXECUTABLE",
        )
        self.assertFalse(readback["attempt_artifact_available"])
        self.assert_safe(readback)

    def test_dispatch_claim_normalizes_to_g6_15_attempt_artifact(self):
        self.prepare()
        result = self.journal.record_dispatch_claim(
            ATTEMPT_ID,
            client_id=82,
            order_id=1001,
            dispatch_evidence_sha256="c" * 64,
            now=NOW + timedelta(seconds=6),
        )
        self.assertEqual(
            result["status"],
            "ATTEMPT_ARTIFACT_READY_NON_EXECUTABLE",
        )
        artifact = result["attempt_artifact"]
        self.assertTrue(artifact["request_dispatched"])
        self.assertFalse(artifact["local_failure_before_dispatch"])
        self.assertEqual(
            artifact["expected_order"],
            {
                "symbol": "NVDA",
                "side": "BUY",
                "quantity": 2,
                "limit_price": 100.0,
            },
        )
        self.assertEqual(artifact["client_id"], 82)
        self.assertEqual(artifact["order_id"], 1001)
        self.assert_safe(result)

        reconciled = reconcile_submission_attempt(
            self.reservation,
            attempt=artifact,
            broker_observation=None,
            now=NOW + timedelta(seconds=7),
        )
        self.assertEqual(
            reconciled["status"],
            "BROKER_OUTCOME_UNKNOWN_DO_NOT_RETRY",
        )
        self.assertFalse(reconciled["automatic_retry_allowed"])

    def test_local_failure_artifact_integrates_with_g6_15(self):
        self.prepare()
        result = self.journal.record_local_failure_before_dispatch(
            ATTEMPT_ID,
            failure_evidence_sha256="d" * 64,
            now=NOW + timedelta(seconds=6),
        )
        artifact = result["attempt_artifact"]
        self.assertFalse(artifact["request_dispatched"])
        self.assertTrue(artifact["local_failure_before_dispatch"])

        reconciled = reconcile_submission_attempt(
            self.reservation,
            attempt=artifact,
            broker_observation=None,
            now=NOW + timedelta(seconds=7),
        )
        self.assertEqual(
            reconciled["status"],
            "LOCAL_FAILURE_BEFORE_BROKER_DISPATCH",
        )
        self.assertFalse(reconciled["automatic_retry_allowed"])

    def test_fake_reservation_not_present_in_g6_14_ledger_blocks(self):
        fake = dict(self.reservation)
        fake["authorization_id"] = "33333333-3333-4333-8333-333333333333"
        result = self.journal.prepare(
            fake,
            self.contract,
            self.order_intent,
            TOKEN,
            now=NOW + timedelta(seconds=5),
            attempt_id=ATTEMPT_ID,
        )
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn(
            result["reason"],
            {
                "CONTRACT_RESERVATION_INTENT_MISMATCH",
                "RESERVATION_NOT_FOUND_IN_LEDGER",
                "RESERVATION_LEDGER_BINDING_MISMATCH",
            },
        )
        self.assert_safe(result)

    def test_missing_reservation_ledger_evidence_blocks(self):
        missing = Path(self.directory.name) / "missing-reservation.sqlite3"
        journal = PaperSubmissionAttemptJournal(
            Path(self.directory.name) / "other-attempt.sqlite3",
            missing,
        )
        result = journal.prepare(
            self.reservation,
            self.contract,
            self.order_intent,
            TOKEN,
            now=NOW + timedelta(seconds=5),
            attempt_id=ATTEMPT_ID,
        )
        self.assertEqual(
            result["reason"],
            "RESERVATION_LEDGER_EVIDENCE_REQUIRED",
        )
        self.assert_safe(result)

    def test_modified_intent_or_contract_blocks(self):
        changed_intent = dict(self.order_intent)
        changed_intent["quantity"] = 3
        result = self.journal.prepare(
            self.reservation,
            self.contract,
            changed_intent,
            TOKEN,
            now=NOW + timedelta(seconds=5),
            attempt_id=ATTEMPT_ID,
        )
        self.assertEqual(
            result["reason"],
            "CONTRACT_RESERVATION_INTENT_MISMATCH",
        )

        changed_contract = dict(self.contract)
        changed_contract["shadow_order_sha256"] = "e" * 64
        result = self.journal.prepare(
            self.reservation,
            changed_contract,
            self.order_intent,
            TOKEN,
            now=NOW + timedelta(seconds=5),
            attempt_id=ATTEMPT_ID,
        )
        self.assertEqual(
            result["reason"],
            "CONTRACT_DIGEST_MISMATCH",
        )

    def test_stale_reservation_blocks_new_attempt(self):
        result = self.prepare(
            now=NOW + timedelta(seconds=61),
        )
        self.assertEqual(result["reason"], "RESERVATION_STALE")
        self.assert_safe(result)

    def test_invalid_account_token_blocks(self):
        result = self.journal.prepare(
            self.reservation,
            self.contract,
            self.order_intent,
            "DU1234567",
            now=NOW + timedelta(seconds=5),
            attempt_id=ATTEMPT_ID,
        )
        self.assertEqual(
            result["reason"],
            "INVALID_ACCOUNT_EVIDENCE_TOKEN",
        )
        self.assert_safe(result)

    def test_same_authorization_cannot_prepare_twice(self):
        first = self.prepare()
        second = self.journal.prepare(
            self.reservation,
            self.contract,
            self.order_intent,
            TOKEN,
            now=NOW + timedelta(seconds=5),
            attempt_id="44444444-4444-4444-8444-444444444444",
        )
        self.assertEqual(first["status"], "ATTEMPT_PREPARED_NON_EXECUTABLE")
        self.assertEqual(second["status"], "ATTEMPT_ALREADY_EXISTS")
        self.assertTrue(second["duplicate"])
        self.assertEqual(second["attempt_id"], ATTEMPT_ID)
        self.assert_safe(second)

    def test_concurrent_prepare_allows_exactly_one_attempt(self):
        def prepare_once(index):
            journal = PaperSubmissionAttemptJournal(
                self.attempt_path,
                self.reservation_path,
            )
            return journal.prepare(
                self.reservation,
                self.contract,
                self.order_intent,
                TOKEN,
                now=NOW + timedelta(seconds=5),
                attempt_id=f"55555555-5555-4555-8555-{index:012d}",
            )

        with ThreadPoolExecutor(max_workers=8) as executor:
            results = list(executor.map(prepare_once, range(1, 9)))

        winners = [
            item for item in results
            if item["status"] == "ATTEMPT_PREPARED_NON_EXECUTABLE"
        ]
        duplicates = [
            item for item in results
            if item["status"] == "ATTEMPT_ALREADY_EXISTS"
        ]
        self.assertEqual(len(winners), 1)
        self.assertEqual(len(duplicates), 7)
        self.assertTrue(all(
            item["paper_order_submission_allowed"] is False
            for item in results
        ))

    def test_dispatch_and_local_failure_race_only_one_finalizes(self):
        self.prepare()

        def dispatch():
            return PaperSubmissionAttemptJournal(
                self.attempt_path,
                self.reservation_path,
            ).record_dispatch_claim(
                ATTEMPT_ID,
                client_id=82,
                order_id=1001,
                dispatch_evidence_sha256="c" * 64,
                now=NOW + timedelta(seconds=6),
            )

        def fail():
            return PaperSubmissionAttemptJournal(
                self.attempt_path,
                self.reservation_path,
            ).record_local_failure_before_dispatch(
                ATTEMPT_ID,
                failure_evidence_sha256="d" * 64,
                now=NOW + timedelta(seconds=6),
            )

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda fn: fn(), (dispatch, fail)))

        ready = [
            item for item in results
            if item["status"] == "ATTEMPT_ARTIFACT_READY_NON_EXECUTABLE"
        ]
        finalized = [
            item for item in results
            if item["status"] == "ATTEMPT_FINALIZED"
        ]
        self.assertEqual(len(ready), 1)
        self.assertEqual(len(finalized), 1)
        self.assertTrue(all(
            item["paper_order_submission_allowed"] is False
            for item in results
        ))

    def test_exact_dispatch_retry_is_idempotent(self):
        self.prepare()
        first = self.journal.record_dispatch_claim(
            ATTEMPT_ID,
            client_id=82,
            order_id=1001,
            dispatch_evidence_sha256="c" * 64,
            now=NOW + timedelta(seconds=6),
        )
        second = self.journal.record_dispatch_claim(
            ATTEMPT_ID,
            client_id=82,
            order_id=1001,
            dispatch_evidence_sha256="c" * 64,
            now=NOW + timedelta(seconds=10),
        )
        self.assertEqual(
            first["status"],
            "ATTEMPT_ARTIFACT_READY_NON_EXECUTABLE",
        )
        self.assertEqual(
            second["status"],
            "ATTEMPT_ARTIFACT_READY_NON_EXECUTABLE",
        )
        self.assertTrue(second["duplicate"])
        self.assertEqual(
            first["attempt_artifact"]["attempt_journal_event_sha256"],
            second["attempt_artifact"]["attempt_journal_event_sha256"],
        )

    def test_dispatch_after_local_failure_is_blocked(self):
        self.prepare()
        self.journal.record_local_failure_before_dispatch(
            ATTEMPT_ID,
            failure_evidence_sha256="d" * 64,
            now=NOW + timedelta(seconds=6),
        )
        result = self.journal.record_dispatch_claim(
            ATTEMPT_ID,
            client_id=82,
            order_id=1001,
            dispatch_evidence_sha256="c" * 64,
            now=NOW + timedelta(seconds=7),
        )
        self.assertEqual(result["status"], "ATTEMPT_FINALIZED")
        self.assertEqual(
            result["existing_event_type"],
            "LOCAL_FAILURE_BEFORE_DISPATCH",
        )
        self.assert_safe(result)

    def test_local_failure_after_dispatch_is_blocked(self):
        self.prepare()
        self.journal.record_dispatch_claim(
            ATTEMPT_ID,
            client_id=82,
            order_id=1001,
            dispatch_evidence_sha256="c" * 64,
            now=NOW + timedelta(seconds=6),
        )
        result = self.journal.record_local_failure_before_dispatch(
            ATTEMPT_ID,
            failure_evidence_sha256="d" * 64,
            now=NOW + timedelta(seconds=7),
        )
        self.assertEqual(result["status"], "ATTEMPT_FINALIZED")
        self.assertEqual(
            result["existing_event_type"],
            "DISPATCH_CLAIM_RECORDED",
        )
        self.assert_safe(result)

    def test_invalid_dispatch_identity_or_evidence_blocks(self):
        self.prepare()
        bad_identity = self.journal.record_dispatch_claim(
            ATTEMPT_ID,
            client_id=-1,
            order_id=1001,
            dispatch_evidence_sha256="c" * 64,
            now=NOW + timedelta(seconds=6),
        )
        self.assertEqual(
            bad_identity["reason"],
            "INVALID_BROKER_REQUEST_IDENTITY",
        )

        bad_evidence = self.journal.record_dispatch_claim(
            ATTEMPT_ID,
            client_id=82,
            order_id=1001,
            dispatch_evidence_sha256="bad",
            now=NOW + timedelta(seconds=6),
        )
        self.assertEqual(
            bad_evidence["reason"],
            "INVALID_EVENT_EVIDENCE_DIGEST",
        )

    def test_attempt_journal_unavailable_fails_closed(self):
        parent_file = Path(self.directory.name) / "not-a-directory"
        parent_file.write_text("x", encoding="utf-8")
        journal = PaperSubmissionAttemptJournal(
            parent_file / "attempt.sqlite3",
            self.reservation_path,
        )
        result = journal.prepare(
            self.reservation,
            self.contract,
            self.order_intent,
            TOKEN,
            now=NOW + timedelta(seconds=5),
            attempt_id=ATTEMPT_ID,
        )
        self.assertEqual(
            result["reason"],
            "ATTEMPT_JOURNAL_UNAVAILABLE",
        )
        self.assert_safe(result)


if __name__ == "__main__":
    unittest.main()
