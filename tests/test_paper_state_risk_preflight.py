"""G7.17 offline tests for post-authorization Paper broker-state risk."""

from datetime import datetime, timedelta, timezone
import hashlib
import json
import unittest

from engines.paper_state_risk_preflight import (
    _EXPECTED_G5_CHECKS,
    evaluate_paper_state_risk_preflight,
)


NOW = datetime(
    2026,
    11,
    2,
    12,
    0,
    tzinfo=timezone.utc,
)
AUTHORIZED_RUN_ID = "11111111-1111-4111-8111-111111111111"
FRESH_RUN_ID = "33333333-3333-4333-8333-333333333333"
AUTH_ID = "22222222-2222-4222-8222-222222222222"
ACCOUNT = "IBKR-A1B2C3D4E5"


def digest(payload):
    return hashlib.sha256(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def safe_flags():
    return {
        "broker_submission_allowed": False,
        "paper_order_submission_allowed": False,
        "live_execution_allowed": False,
        "automatic_promotion_allowed": False,
        "real_money_trading_allowed": False,
    }


def required_g2_checks():
    return [
        {
            "check": "paper_mode_only",
            "required": True,
            "passed": True,
        },
        {
            "check": "gateway_connected",
            "required": True,
            "passed": True,
        },
    ]


def g2(
    *,
    now,
    run_id,
    available_funds=10000.0,
    currency="USD",
    account=ACCOUNT,
    positions=None,
    open_orders=None,
):
    positions = (
        positions
        if positions is not None
        else [
            {
                "account": account,
                "symbol": "BKR",
                "security_type": "STK",
                "currency": "USD",
                "exchange": "SMART",
                "position": 10.0,
                "average_cost": 40.0,
            }
        ]
    )
    open_orders = (
        open_orders
        if open_orders is not None
        else []
    )

    stamp = (
        now
        -
        timedelta(
            seconds=5
        )
    ).isoformat()

    return {
        "evidence_run_id": run_id,
        "run_mode": {
            "requested_mode": "READ_ONLY",
            "mode": "READ_ONLY",
            "mode_valid": True,
            "live_execution_allowed": False,
            "paper_order_submission_requested": False,
            "dry_run": False,
            "read_only": True,
            "safe_off": False,
        },
        "snapshot": {
            "timestamp": stamp,
            "status": "CONNECTED",
            "connection_status": "CONNECTED",
            "config": {
                "enabled": True,
                "mode": "PAPER",
                "mode_valid": True,
                "host": "127.0.0.1",
                "port": 4002,
                "read_only": True,
                "live_trading_allowed": False,
                "endpoint_safe": True,
            },
            "order_submission_hard_blocked": True,
            "gateway_read_only_configuration_independently_attested": True,
            "live_trading_allowed": False,
            "requests_complete": {
                "managed_accounts": True,
                "account_summary": True,
                "positions": True,
                "open_orders": True,
            },
            "paper_account_guard": {
                "paper_account_verified": True,
                "verified_account_fingerprints": [
                    account
                ],
            },
            "account_summary_account_fingerprints": [
                account
            ],
            "account_summary": {
                "AvailableFunds": {
                    "value": available_funds,
                    "currency": currency,
                }
            },
            "positions": positions,
            "open_orders": open_orders,
        },
        "gateway_read_only_attestation": {
            "status": "VERIFIED",
            "verified": True,
            "gateway_read_only_configuration_independently_attested": True,
            "failure_reasons": [],
            "attestation_id": "44444444-4444-4444-8444-444444444444",
            "reviewer_id": "aurora-independent-reviewer",
            "git_sha": "a" * 40,
            "evidence_sha256": "b" * 64,
            "gcp_project_id": "project-ce9773ef-6814-469c-92b",
            "gcp_instance_id": "1234567890123456789",
            **safe_flags(),
        },
        "readiness": {
            "timestamp": stamp,
            "readiness": "READY_FOR_PAPER_READ_ONLY",
            "required_failure_count": 0,
            "checks": required_g2_checks(),
            "paper_order_submission_allowed": False,
            "live_execution_allowed": False,
            "gateway_read_only_configuration_independently_attested": True,
            "account_metrics": {
                "net_liquidation": 20000.0,
                "total_cash_value": 10000.0,
                "available_funds": available_funds,
                "buying_power": 40000.0,
            },
        },
    }


def authorized_g2():
    return g2(
        now=(
            NOW
            -
            timedelta(
                seconds=20
            )
        ),
        run_id=AUTHORIZED_RUN_ID,
    )


def fresh_g2(
    **kwargs,
):
    values = {
        "now": NOW,
        "run_id": FRESH_RUN_ID,
    }
    values.update(
        kwargs
    )
    return g2(
        **values
    )


def shadow(
    *,
    action="BUY",
    quantity=1,
    limit_price=50.0,
):
    return {
        "shadow_order_id": "shadow-001",
        "idempotency_key": "intent-001",
        "symbol": "BKR",
        "asset_type": "STK",
        "action": action,
        "quantity": quantity,
        "order_type": "LIMIT",
        "time_in_force": "DAY",
        "limit_price": limit_price,
        "order_notional_usd": round(
            quantity
            *
            limit_price,
            2,
        ),
        "status": "SHADOW_ACCEPTED",
        **safe_flags(),
    }


def completion(
    authorized_proof,
    order,
):
    return {
        "status": "PAPER_RUNTIME_VALIDATED_SHADOW_ONLY",
        "next_gate": "MANUAL_PAPER_ORDER_AUTHORIZATION_NOT_GRANTED",
        "failure_reasons": [],
        "checks": {
            "g2_readiness_proof_bound": True,
            "gateway_attestation_runtime_verified": True,
            "gateway_attestation_g2_runtime_bound": True,
            "gateway_attestation_readiness_bound": True,
            "g4_shadow_order_payload_valid": True,
            "g4_shadow_order_ledger_payload_bound": True,
        },
        "evidence_binding": {
            "g2_paper_read_only_proof_sha256": digest(
                authorized_proof
            ),
            "g4_shadow_order_sha256": digest(
                order
            ),
        },
        **safe_flags(),
    }


def authorization_result(
    comp,
    order,
):
    return {
        "status": "MANUAL_PAPER_AUTHORIZATION_VALIDATED",
        "authorization_id": AUTH_ID,
        "scope": "ONE_PAPER_ORDER",
        "mode": "PAPER",
        "authorization_issued_at": (
            NOW
            -
            timedelta(
                seconds=10
            )
        ).isoformat(),
        "authorization_expires_at": (
            NOW
            +
            timedelta(
                minutes=5
            )
        ).isoformat(),
        "completion_status_sha256": digest(
            comp
        ),
        "shadow_order_sha256": digest(
            order
        ),
        "checks": {
            name: True
            for name in _EXPECTED_G5_CHECKS
        },
        "authorization_can_be_consumed_once": True,
        "next_gate": "PAPER_EXECUTION_CONNECTOR_REVIEW_REQUIRED",
        **safe_flags(),
    }


class PaperStateRiskPreflightTests(unittest.TestCase):
    def evaluate(
        self,
        *,
        authorized=None,
        fresh=None,
        order=None,
        comp=None,
        auth=None,
        now=NOW,
        max_g2_age_seconds=60,
    ):
        authorized = (
            authorized
            if authorized is not None
            else authorized_g2()
        )
        fresh = (
            fresh
            if fresh is not None
            else fresh_g2()
        )
        order = (
            order
            if order is not None
            else shadow()
        )
        comp = (
            comp
            if comp is not None
            else completion(
                authorized,
                order,
            )
        )
        auth = (
            auth
            if auth is not None
            else authorization_result(
                comp,
                order,
            )
        )

        return evaluate_paper_state_risk_preflight(
            authorized,
            fresh,
            comp,
            order,
            auth,
            now=now,
            max_g2_age_seconds=max_g2_age_seconds,
        )

    def test_buy_passes_with_post_authorization_fresh_funds(self):
        result = self.evaluate()

        self.assertEqual(
            result["status"],
            "PAPER_STATE_RISK_VALIDATED_NON_EXECUTABLE",
        )
        self.assertTrue(
            result["checks"][
                "fresh_g2_post_authorization"
            ]
        )
        self.assertTrue(
            result["checks"][
                "buy_available_funds_sufficient"
            ]
        )

        for name, value in safe_flags().items():
            self.assertIs(
                result[name],
                value,
            )

        def collect_keys(value):
            keys = set()

            if isinstance(value, dict):
                for key, child in value.items():
                    keys.add(key)
                    keys.update(
                        collect_keys(
                            child
                        )
                    )
            elif isinstance(value, list):
                for child in value:
                    keys.update(
                        collect_keys(
                            child
                        )
                    )

            return keys

        output_keys = collect_keys(
            result
        )

        self.assertNotIn(
            "available_funds",
            output_keys,
        )
        self.assertNotIn(
            "account_summary",
            output_keys,
        )
        self.assertNotIn(
            "positions",
            output_keys,
        )

    def test_fresh_buy_insufficient_funds_blocks_even_if_authorized_g2_had_cash(self):
        fresh = fresh_g2(
            available_funds=25.0,
        )

        result = self.evaluate(
            fresh=fresh,
        )

        self.assertEqual(
            result["status"],
            "BLOCKED",
        )
        self.assertIn(
            "buy_available_funds_sufficient",
            result["failure_reasons"],
        )

    def test_sell_subtracts_existing_open_sell_quantity(self):
        order = shadow(
            action="SELL",
            quantity=5,
        )
        fresh = fresh_g2(
            positions=[
                {
                    "account": ACCOUNT,
                    "symbol": "BKR",
                    "security_type": "STK",
                    "position": 10.0,
                }
            ],
            open_orders=[
                {
                    "order_id": 10,
                    "account": ACCOUNT,
                    "symbol": "BKR",
                    "security_type": "STK",
                    "action": "SELL",
                    "quantity": 6.0,
                }
            ],
        )

        result = self.evaluate(
            fresh=fresh,
            order=order,
        )

        self.assertEqual(
            result["status"],
            "BLOCKED",
        )
        self.assertIn(
            "sell_inventory_sufficient",
            result["failure_reasons"],
        )

    def test_sell_passes_without_shorting_or_double_reserving(self):
        order = shadow(
            action="SELL",
            quantity=4,
        )
        fresh = fresh_g2(
            open_orders=[
                {
                    "order_id": 10,
                    "account": ACCOUNT,
                    "symbol": "BKR",
                    "security_type": "STK",
                    "action": "SELL",
                    "quantity": 6.0,
                }
            ],
        )

        result = self.evaluate(
            fresh=fresh,
            order=order,
        )

        self.assertEqual(
            result["status"],
            "PAPER_STATE_RISK_VALIDATED_NON_EXECUTABLE",
        )
        self.assertTrue(
            result["checks"][
                "sell_inventory_sufficient"
            ]
        )

    def test_malformed_or_wrong_account_open_order_blocks(self):
        malformed = fresh_g2(
            open_orders=[
                {
                    "order_id": 10,
                    "account": ACCOUNT,
                    "symbol": "AMD",
                    "security_type": "STK",
                    "action": "SELL",
                    "quantity": True,
                }
            ],
        )

        first = self.evaluate(
            fresh=malformed,
        )

        self.assertIn(
            "broker_state_payload_valid",
            first["failure_reasons"],
        )

        wrong_account = fresh_g2(
            open_orders=[
                {
                    "order_id": 10,
                    "account": "IBKR-FFFFFFFFFF",
                    "symbol": "AMD",
                    "security_type": "STK",
                    "action": "SELL",
                    "quantity": 1.0,
                }
            ],
        )

        second = self.evaluate(
            fresh=wrong_account,
        )

        self.assertIn(
            "broker_state_payload_valid",
            second["failure_reasons"],
        )

    def test_stale_fresh_g2_blocks_even_when_authorized_proof_is_valid(self):
        stale = fresh_g2(
            now=(
                NOW
                -
                timedelta(
                    seconds=61
                )
            )
        )

        result = self.evaluate(
            fresh=stale,
        )

        self.assertEqual(
            result["status"],
            "BLOCKED",
        )
        self.assertIn(
            "fresh_g2_broker_state_fresh",
            result["failure_reasons"],
        )

    def test_fresh_g2_must_be_post_authorization(self):
        pre_auth = fresh_g2(
            now=(
                NOW
                -
                timedelta(
                    seconds=20
                )
            )
        )

        result = self.evaluate(
            fresh=pre_auth,
        )

        self.assertIn(
            "fresh_g2_post_authorization",
            result["failure_reasons"],
        )

    def test_fresh_g2_must_match_authorized_attestation_and_account(self):
        fresh = fresh_g2()
        fresh[
            "gateway_read_only_attestation"
        ][
            "evidence_sha256"
        ] = "c" * 64

        first = self.evaluate(
            fresh=fresh,
        )

        self.assertIn(
            "fresh_g2_identity_matches_authorized",
            first["failure_reasons"],
        )

        fresh = fresh_g2(
            account="IBKR-FEDCBA9876",
            positions=[
                {
                    "account": "IBKR-FEDCBA9876",
                    "symbol": "BKR",
                    "security_type": "STK",
                    "position": 10.0,
                }
            ],
        )

        second = self.evaluate(
            fresh=fresh,
        )

        self.assertIn(
            "fresh_g2_identity_matches_authorized",
            second["failure_reasons"],
        )

    def test_completion_must_bind_exact_authorized_g2_and_shadow(self):
        authorized = authorized_g2()
        order = shadow()
        comp = completion(
            authorized,
            order,
        )
        auth = authorization_result(
            comp,
            order,
        )

        authorized[
            "snapshot"
        ][
            "positions"
        ][0][
            "position"
        ] = 11.0

        first = self.evaluate(
            authorized=authorized,
            order=order,
            comp=comp,
            auth=auth,
        )

        self.assertIn(
            "completion_authorized_g2_digest_bound",
            first["failure_reasons"],
        )

        authorized = authorized_g2()
        order = shadow()
        comp = completion(
            authorized,
            order,
        )
        auth = authorization_result(
            comp,
            order,
        )

        order["quantity"] = 2
        order["order_notional_usd"] = 100.0

        second = self.evaluate(
            authorized=authorized,
            order=order,
            comp=comp,
            auth=auth,
        )

        self.assertIn(
            "completion_shadow_digest_bound",
            second["failure_reasons"],
        )
        self.assertIn(
            "authorization_shadow_digest_bound",
            second["failure_reasons"],
        )

    def test_expired_g5_authorization_blocks(self):
        authorized = authorized_g2()
        order = shadow()
        comp = completion(
            authorized,
            order,
        )
        auth = authorization_result(
            comp,
            order,
        )
        auth["authorization_expires_at"] = (
            NOW
            -
            timedelta(
                seconds=1
            )
        ).isoformat()

        result = self.evaluate(
            authorized=authorized,
            order=order,
            comp=comp,
            auth=auth,
        )

        self.assertIn(
            "authorization_current",
            result["failure_reasons"],
        )

    def test_invalid_clock_non_usd_and_relaxed_freshness_block(self):
        bad_clock = self.evaluate(
            now="not-a-clock",
        )
        self.assertIn(
            "reference_clock_valid",
            bad_clock["failure_reasons"],
        )

        non_usd = self.evaluate(
            fresh=fresh_g2(
                currency="QAR",
            ),
        )
        self.assertIn(
            "broker_state_payload_valid",
            non_usd["failure_reasons"],
        )
        self.assertIn(
            "buy_available_funds_sufficient",
            non_usd["failure_reasons"],
        )

        relaxed = self.evaluate(
            max_g2_age_seconds=120,
        )
        self.assertIn(
            "risk_policy_valid",
            relaxed["failure_reasons"],
        )

    def test_unsafe_permission_missing_g5_check_or_bad_notional_blocks(self):
        authorized = authorized_g2()
        order = shadow()
        comp = completion(
            authorized,
            order,
        )
        auth = authorization_result(
            comp,
            order,
        )
        auth[
            "paper_order_submission_allowed"
        ] = True

        unsafe = self.evaluate(
            authorized=authorized,
            order=order,
            comp=comp,
            auth=auth,
        )
        self.assertIn(
            "authorization_validated",
            unsafe["failure_reasons"],
        )

        auth = authorization_result(
            comp,
            order,
        )
        auth[
            "checks"
        ].pop(
            "completion_shadow_order_digest_bound"
        )

        missing = self.evaluate(
            authorized=authorized,
            order=order,
            comp=comp,
            auth=auth,
        )
        self.assertIn(
            "authorization_validated",
            missing["failure_reasons"],
        )

        bad_order = shadow()
        bad_order[
            "order_notional_usd"
        ] = 49.0

        bad_notional = self.evaluate(
            order=bad_order,
        )
        self.assertIn(
            "shadow_order_shape_valid",
            bad_notional["failure_reasons"],
        )


if __name__ == "__main__":
    unittest.main()
