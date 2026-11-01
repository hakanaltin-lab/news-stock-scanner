"""Offline safety tests for G6.14 authorization reservation ledger."""

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
    validate_reservable_contract,
)
from engines.paper_order_authorization_gate import (
    AUTH_VERSION,
    evaluate_manual_paper_authorization,
)
from engines.paper_portfolio_risk import evaluate_portfolio_intent
from engines.paper_submission_contract import evaluate_paper_submission_contract


NOW = datetime(2026, 11, 1, 13, 30, tzinfo=timezone.utc)


def digest(payload):
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def intent(idempotency_key="paper-reserve-0001"):
    return {
        "symbol": "NVDA",
        "side": "BUY",
        "order_type": "LMT",
        "quantity": 1,
        "limit_price": 100.0,
        "idempotency_key": idempotency_key,
    }


def shadow(order_intent, shadow_order_id="shadow-reserve-1"):
    return {
        "status": "SHADOW_ACCEPTED",
        "shadow_order_id": shadow_order_id,
        "idempotency_key": order_intent["idempotency_key"],
        "symbol": order_intent["symbol"],
        "asset_type": "STK",
        "action": order_intent["side"],
        "quantity": order_intent["quantity"],
        "order_type": "LIMIT",
        "time_in_force": "DAY",
        "limit_price": order_intent["limit_price"],
        "broker_submission_allowed": False,
        "paper_order_submission_allowed": False,
        "live_execution_allowed": False,
        "automatic_promotion_allowed": False,
    }


def completion():
    return {
        "status": "PAPER_RUNTIME_VALIDATED_SHADOW_ONLY",
        "next_gate": "MANUAL_PAPER_ORDER_AUTHORIZATION_NOT_GRANTED",
        "broker_submission_allowed": False,
        "paper_order_submission_allowed": False,
        "live_execution_allowed": False,
        "automatic_promotion_allowed": False,
    }


def make_contract(
    idempotency_key="paper-reserve-0001",
    authorization_id="11111111-1111-4111-8111-111111111111",
    shadow_order_id="shadow-reserve-1",
    contract_now=NOW,
):
    order_intent = intent(idempotency_key)
    reviewed_shadow = shadow(order_intent, shadow_order_id)
    comp = completion()
    auth_time = contract_now - timedelta(seconds=5)
    authorization = {
        "version": AUTH_VERSION,
        "authorization_id": authorization_id,
        "approved": True,
        "mode": "PAPER",
        "scope": "ONE_PAPER_ORDER",
        "issued_at": (auth_time - timedelta(seconds=10)).isoformat(),
        "expires_at": (auth_time + timedelta(minutes=5)).isoformat(),
        "completion_status_sha256": digest(comp),
        "shadow_order_sha256": digest(reviewed_shadow),
        "live_execution_allowed": False,
        "automatic_promotion_allowed": False,
    }
    auth_result = evaluate_manual_paper_authorization(
        comp,
        reviewed_shadow,
        authorization,
        now=auth_time,
    )

    context = {
        "mode": "PAPER",
        "live_trading_allowed": False,
        "broker_read_only": True,
        "paper_account_verified": True,
        "kill_switch_engaged": True,
        "paper_account_fingerprint": "PAPER-REDACTED",
    }
    portfolio = {
        "snapshot_verified": True,
        "snapshot_fresh": True,
        "snapshot_generated_at_utc": (contract_now - timedelta(seconds=5)).isoformat(),
        "paper_account_fingerprint": "PAPER-REDACTED",
        "equity_usd": 1000,
        "gross_exposure_usd": 300,
        "pending_notional_usd": 100,
        "pending_orders": [{
            "symbol": "AMD",
            "side": "BUY",
            "quantity": 1,
            "limit_price": 100.0,
            "idempotency_key": "existing-pending-0001",
        }],
        "known_idempotency_keys": [],
    }
    risk_result = evaluate_portfolio_intent(
        order_intent,
        context,
        portfolio,
        now_utc=contract_now,
    )
    result = evaluate_paper_submission_contract(
        auth_result,
        risk_result,
        order_intent,
        reviewed_shadow,
        consumed_authorization_ids=[],
        now=contract_now,
    )
    if result.get("status") != "SUBMISSION_CONTRACT_VALIDATED_NON_EXECUTABLE":
        raise AssertionError(result)
    return result


class AuthorizationReservationLedgerTests(unittest.TestCase):
    def test_valid_contract_is_reserved_once_and_remains_non_executable(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "reservations.sqlite3"
            result = PaperAuthorizationReservationLedger(path).reserve(
                make_contract(),
                now=NOW,
            )
            self.assertEqual(
                result["status"],
                "AUTHORIZATION_RESERVED_NON_EXECUTABLE",
            )
            self.assertTrue(result["reserved"])
            self.assertFalse(result["paper_order_submission_allowed"])
            self.assertFalse(result["live_execution_allowed"])
            self.assertFalse(result["broker_order_object_allowed"])
            self.assertEqual(
                result["next_gate"],
                "PAPER_BROKER_ADAPTER_REVIEW_AND_FAILURE_SEMANTICS_REQUIRED",
            )
            self.assertEqual(stat.S_IMODE(os.stat(path).st_mode), 0o600)

    def test_same_contract_cannot_be_reserved_twice(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = PaperAuthorizationReservationLedger(
                Path(directory) / "reservations.sqlite3"
            )
            contract = make_contract()
            first = ledger.reserve(contract, now=NOW)
            second = ledger.reserve(contract, now=NOW)
            self.assertTrue(first["reserved"])
            self.assertFalse(second["reserved"])
            self.assertTrue(second["duplicate"])
            self.assertEqual(
                second["reason"],
                "AUTHORIZATION_OR_ORDER_ALREADY_RESERVED",
            )

    def test_concurrent_replay_allows_exactly_one_reservation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "reservations.sqlite3"
            contract = make_contract()

            def reserve_once(_):
                return PaperAuthorizationReservationLedger(path).reserve(
                    contract,
                    now=NOW,
                )

            with ThreadPoolExecutor(max_workers=8) as executor:
                results = list(executor.map(reserve_once, range(8)))

            winners = [item for item in results if item.get("reserved") is True]
            blocked = [item for item in results if item.get("reserved") is False]
            self.assertEqual(len(winners), 1)
            self.assertEqual(len(blocked), 7)
            self.assertTrue(all(
                item["paper_order_submission_allowed"] is False
                and item["live_execution_allowed"] is False
                for item in results
            ))

    def test_same_idempotency_with_new_authorization_is_blocked(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = PaperAuthorizationReservationLedger(
                Path(directory) / "reservations.sqlite3"
            )
            first = make_contract()
            second = make_contract(
                authorization_id="22222222-2222-4222-8222-222222222222",
                shadow_order_id="shadow-reserve-2",
            )
            self.assertTrue(ledger.reserve(first, now=NOW)["reserved"])
            blocked = ledger.reserve(second, now=NOW)
            self.assertFalse(blocked["reserved"])
            self.assertEqual(
                blocked["reason"],
                "AUTHORIZATION_OR_ORDER_ALREADY_RESERVED",
            )

    def test_stale_contract_is_not_reservable(self):
        contract = make_contract()
        result = validate_reservable_contract(
            contract,
            now=NOW + timedelta(seconds=31),
        )
        self.assertEqual(result["status"], "BLOCKED")
        self.assertFalse(result["checks"]["contract_time_valid"])

    def test_future_contract_beyond_clock_tolerance_blocks(self):
        contract = make_contract(contract_now=NOW + timedelta(seconds=3))
        result = validate_reservable_contract(contract, now=NOW)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertFalse(result["checks"]["contract_time_valid"])

    def test_tampered_contract_digest_blocks_before_persistence(self):
        contract = make_contract()
        contract["idempotency_key"] = "paper-reserve-tampered"
        result = validate_reservable_contract(contract, now=NOW)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertFalse(result["checks"]["contract_digest_self_consistent"])

    def test_unsafe_submission_flag_blocks(self):
        contract = make_contract()
        contract["paper_order_submission_allowed"] = True
        result = validate_reservable_contract(contract, now=NOW)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertFalse(result["checks"]["submission_flags_safe"])

    def test_missing_or_invalid_contract_fields_block(self):
        for mutation in (
            ("authorization_id", "not-a-uuid"),
            ("intent_sha256", "bad"),
            ("shadow_order_sha256", "bad"),
            ("contract_sha256", "bad"),
            ("idempotency_key", ""),
            ("version", "UNKNOWN"),
        ):
            with self.subTest(mutation=mutation):
                contract = make_contract()
                contract[mutation[0]] = mutation[1]
                result = validate_reservable_contract(contract, now=NOW)
                self.assertEqual(result["status"], "BLOCKED")

    def test_unavailable_ledger_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            parent_file = Path(directory) / "not-a-directory"
            parent_file.write_text("x", encoding="utf-8")
            path = parent_file / "reservations.sqlite3"
            result = PaperAuthorizationReservationLedger(path).reserve(
                make_contract(),
                now=NOW,
            )
            self.assertEqual(result["status"], "BLOCKED")
            self.assertEqual(result["reason"], "LEDGER_UNAVAILABLE")
            self.assertFalse(result["paper_order_submission_allowed"])


if __name__ == "__main__":
    unittest.main()
