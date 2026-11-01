"""Offline tests for G6.18 adapter review envelope."""

from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from engines.paper_adapter_review_envelope import (
    PaperAdapterReviewEnvelopeBuilder,
)
from engines.paper_authorization_reservation_ledger import (
    PaperAuthorizationReservationLedger,
)
from engines.paper_submission_attempt_journal import (
    PaperSubmissionAttemptJournal,
)
from engines.paper_submission_contract import CONTRACT_VERSION


NOW = datetime(2026, 11, 1, 17, 0, tzinfo=timezone.utc)
AUTH_ID = "11111111-1111-4111-8111-111111111111"
ATTEMPT_ID = "22222222-2222-4222-8222-222222222222"
TOKEN = "IBKR-EVID-ABCDEF1234567890"


def digest(payload):
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def intent():
    return {
        "symbol": "NVDA",
        "side": "BUY",
        "order_type": "LMT",
        "quantity": 2,
        "limit_price": 100.0,
        "idempotency_key": "paper-envelope-0001",
    }


def contract(order_intent):
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
        "generated_at": (NOW - timedelta(seconds=5)).isoformat(),
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


class AdapterReviewEnvelopeTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name)
        self.reservation_path = root / "reservation.sqlite3"
        self.attempt_path = root / "attempt.sqlite3"
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
        prepared = self.journal.prepare(
            self.reservation,
            self.contract,
            self.order_intent,
            TOKEN,
            now=NOW + timedelta(seconds=5),
            attempt_id=ATTEMPT_ID,
        )
        if prepared.get("status") != "ATTEMPT_PREPARED_NON_EXECUTABLE":
            raise AssertionError(prepared)

        self.builder = PaperAdapterReviewEnvelopeBuilder(
            self.attempt_path
        )

    def tearDown(self):
        self.directory.cleanup()

    def assert_safe(self, result):
        self.assertFalse(result["broker_submission_allowed"])
        self.assertFalse(result["paper_order_submission_allowed"])
        self.assertFalse(result["live_execution_allowed"])
        self.assertFalse(result["automatic_retry_allowed"])
        self.assertFalse(result["automatic_cancel_allowed"])
        self.assertFalse(result["automatic_modify_allowed"])
        self.assertFalse(result["broker_order_object_allowed"])
        self.assertFalse(result["broker_request_materialization_allowed"])

    def test_prepared_attempt_builds_review_only_envelope(self):
        result = self.builder.build(
            ATTEMPT_ID,
            now=NOW + timedelta(seconds=6),
        )
        self.assertEqual(
            result["status"],
            "ADAPTER_REVIEW_ENVELOPE_VALIDATED_NON_EXECUTABLE",
        )
        self.assertEqual(
            result["order"],
            {
                "symbol": "NVDA",
                "side": "BUY",
                "asset_type": "STK",
                "order_type": "LMT",
                "time_in_force": "DAY",
                "quantity": 2,
                "limit_price": 100.0,
            },
        )
        self.assertEqual(
            result["next_gate"],
            "IBKR_PAPER_ADAPTER_IMPLEMENTATION_REVIEW_REQUIRED",
        )
        self.assertEqual(len(result["review_envelope_sha256"]), 64)
        self.assert_safe(result)

    def test_envelope_is_bound_to_account_and_upstream_digests(self):
        result = self.builder.build(
            ATTEMPT_ID,
            now=NOW + timedelta(seconds=6),
        )
        self.assertEqual(
            result["paper_account_evidence_token"],
            TOKEN,
        )
        self.assertEqual(
            result["contract_sha256"],
            self.reservation["contract_sha256"],
        )
        self.assertEqual(
            result["reservation_receipt_sha256"],
            self.reservation["reservation_receipt_sha256"],
        )
        self.assertEqual(
            result["idempotency_key"],
            self.order_intent["idempotency_key"],
        )
        self.assert_safe(result)

    def test_finalized_attempt_cannot_build_new_review_envelope(self):
        finalized = self.journal.record_dispatch_claim(
            ATTEMPT_ID,
            client_id=82,
            order_id=1001,
            dispatch_evidence_sha256="c" * 64,
            now=NOW + timedelta(seconds=7),
        )
        self.assertEqual(
            finalized["status"],
            "ATTEMPT_ARTIFACT_READY_NON_EXECUTABLE",
        )
        result = self.builder.build(
            ATTEMPT_ID,
            now=NOW + timedelta(seconds=8),
        )
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(
            result["reason"],
            "ATTEMPT_NOT_IN_PREPARED_REVIEW_STATE",
        )
        self.assert_safe(result)

    def test_local_failure_finalized_attempt_cannot_build_envelope(self):
        self.journal.record_local_failure_before_dispatch(
            ATTEMPT_ID,
            failure_evidence_sha256="d" * 64,
            now=NOW + timedelta(seconds=7),
        )
        result = self.builder.build(
            ATTEMPT_ID,
            now=NOW + timedelta(seconds=8),
        )
        self.assertEqual(
            result["reason"],
            "ATTEMPT_NOT_IN_PREPARED_REVIEW_STATE",
        )
        self.assert_safe(result)

    def test_stale_prepared_attempt_blocks(self):
        result = self.builder.build(
            ATTEMPT_ID,
            now=NOW + timedelta(seconds=36),
        )
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(
            result["reason"],
            "PREPARED_ATTEMPT_STALE",
        )
        self.assert_safe(result)

    def test_tampered_expected_order_json_is_detected(self):
        connection = sqlite3.connect(str(self.attempt_path))
        try:
            connection.execute(
                """
                UPDATE submission_attempt_registry
                SET expected_order_json = ?
                WHERE attempt_id = ?
                """,
                (
                    json.dumps({
                        "symbol": "AMD",
                        "side": "BUY",
                        "quantity": 2,
                        "limit_price": 100.0,
                    }),
                    ATTEMPT_ID,
                ),
            )
            connection.commit()
        finally:
            connection.close()

        result = self.builder.build(
            ATTEMPT_ID,
            now=NOW + timedelta(seconds=6),
        )
        self.assertEqual(
            result["reason"],
            "EXPECTED_ORDER_DIGEST_MISMATCH",
        )
        self.assert_safe(result)

    def test_tampered_prepare_event_digest_is_detected(self):
        connection = sqlite3.connect(str(self.attempt_path))
        try:
            connection.execute(
                """
                UPDATE submission_attempt_events
                SET event_sha256 = ?
                WHERE attempt_id = ?
                """,
                ("f" * 64, ATTEMPT_ID),
            )
            connection.commit()
        finally:
            connection.close()

        result = self.builder.build(
            ATTEMPT_ID,
            now=NOW + timedelta(seconds=6),
        )
        self.assertEqual(
            result["reason"],
            "PREPARE_EVENT_DIGEST_MISMATCH",
        )
        self.assert_safe(result)

    def test_tampered_prepare_event_time_is_detected(self):
        connection = sqlite3.connect(str(self.attempt_path))
        try:
            connection.execute(
                """
                UPDATE submission_attempt_events
                SET event_time = ?
                WHERE attempt_id = ?
                """,
                (
                    (NOW + timedelta(seconds=4)).isoformat(),
                    ATTEMPT_ID,
                ),
            )
            connection.commit()
        finally:
            connection.close()

        result = self.builder.build(
            ATTEMPT_ID,
            now=NOW + timedelta(seconds=6),
        )
        self.assertEqual(
            result["reason"],
            "PREPARE_EVENT_TIME_MISMATCH",
        )
        self.assert_safe(result)

    def test_invalid_attempt_id_blocks(self):
        result = self.builder.build(
            "not-a-uuid",
            now=NOW + timedelta(seconds=6),
        )
        self.assertEqual(
            result["reason"],
            "INVALID_ATTEMPT_ID",
        )
        self.assert_safe(result)

    def test_missing_attempt_journal_blocks(self):
        builder = PaperAdapterReviewEnvelopeBuilder(
            Path(self.directory.name) / "missing.sqlite3"
        )
        result = builder.build(
            ATTEMPT_ID,
            now=NOW + timedelta(seconds=6),
        )
        self.assertEqual(
            result["reason"],
            "ATTEMPT_JOURNAL_UNAVAILABLE",
        )
        self.assert_safe(result)

    def test_invalid_evaluation_time_blocks(self):
        result = self.builder.build(
            ATTEMPT_ID,
            now="not-a-time",
        )
        self.assertEqual(
            result["reason"],
            "INVALID_EVALUATION_TIME",
        )
        self.assert_safe(result)

    def test_same_inputs_and_time_produce_same_review_digest(self):
        first = self.builder.build(
            ATTEMPT_ID,
            now=NOW + timedelta(seconds=6),
        )
        second = self.builder.build(
            ATTEMPT_ID,
            now=NOW + timedelta(seconds=6),
        )
        self.assertEqual(
            first["review_envelope_sha256"],
            second["review_envelope_sha256"],
        )
        self.assert_safe(first)
        self.assert_safe(second)


if __name__ == "__main__":
    unittest.main()
