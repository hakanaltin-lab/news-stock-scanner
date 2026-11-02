"""G7.17 fail-closed Paper broker-state risk preflight.

This module is non-executable. It consumes already-bound G2/G4/G5 evidence,
rechecks freshness and exact digests, and evaluates BUY cash / SELL inventory
against the read-only Paper broker snapshot. It never submits or reserves an
order and never enables execution permissions.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import hmac
import json
import math
from uuid import UUID


ENGINE_VERSION = "AURORA G7.17 Paper State-Risk Preflight"
DEFAULT_MAX_G2_AGE_SECONDS = 60.0
DEFAULT_MAX_AUTH_LIFETIME_SECONDS = 600.0

_PERMISSION_FLAGS = (
    "broker_submission_allowed",
    "paper_order_submission_allowed",
    "live_execution_allowed",
    "automatic_promotion_allowed",
    "real_money_trading_allowed",
)

_REQUIRED_COMPLETION_CHECKS = (
    "g2_readiness_proof_bound",
    "gateway_attestation_runtime_verified",
    "gateway_attestation_g2_runtime_bound",
    "gateway_attestation_readiness_bound",
    "g4_shadow_order_payload_valid",
    "g4_shadow_order_ledger_payload_bound",
)

_EXPECTED_G5_CHECKS = {
    "completion_validated_shadow_only",
    "shadow_order_accepted",
    "authorization_version",
    "explicit_human_approval",
    "paper_mode_only",
    "single_order_scope",
    "authorization_id_uuid4",
    "authorization_current",
    "completion_digest_bound",
    "shadow_order_digest_bound",
    "completion_shadow_order_digest_bound",
    "no_live_or_automatic_promotion",
}


def _digest(payload):
    try:
        encoded = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    except (
        TypeError,
        ValueError,
        OverflowError,
    ):
        return None

    return hashlib.sha256(
        encoded
    ).hexdigest()


def _utc_datetime(value):
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        text = value.strip()

        if not text:
            return None

        if text.endswith("Z"):
            text = text[:-1] + "+00:00"

        try:
            parsed = datetime.fromisoformat(
                text
            )
        except ValueError:
            return None
    else:
        return None

    if parsed.tzinfo is None:
        return None

    return parsed.astimezone(
        timezone.utc
    )


def _age_seconds(value, now):
    parsed = _utc_datetime(
        value
    )

    if parsed is None:
        return None

    age = (
        now
        -
        parsed
    ).total_seconds()

    if age < -2:
        return None

    return max(
        age,
        0.0,
    )


def _safe_number(value):
    if isinstance(
        value,
        bool,
    ):
        return None

    if not isinstance(
        value,
        (int, float),
    ):
        return None

    parsed = float(
        value
    )

    if not math.isfinite(
        parsed
    ):
        return None

    return parsed


def _safe_flags(payload):
    return (
        isinstance(
            payload,
            dict,
        )
        and all(
            name in payload
            and payload.get(
                name
            )
            is False
            for name in _PERMISSION_FLAGS
        )
    )


def _uuid4(value):
    if not isinstance(
        value,
        str,
    ):
        return None

    text = value.strip()

    try:
        parsed = UUID(
            text
        )
    except (
        ValueError,
        AttributeError,
    ):
        return None

    if (
        parsed.version
        !=
        4
        or str(
            parsed
        )
        !=
        text
    ):
        return None

    return text


def _blocked(
    checks,
    failures,
    digests,
):
    return {
        "engine":
        ENGINE_VERSION,

        "status":
        "BLOCKED",

        "checks":
        checks,

        "failure_reasons":
        failures,

        "evidence_binding":
        digests,

        "risk_summary": {
            "buy_available_funds_sufficient":
            (
                checks.get(
                    "buy_available_funds_sufficient"
                )
                if "buy_available_funds_sufficient"
                in checks
                else None
            ),

            "sell_inventory_sufficient":
            (
                checks.get(
                    "sell_inventory_sufficient"
                )
                if "sell_inventory_sufficient"
                in checks
                else None
            ),

            "broker_state_fresh":
            checks.get(
                "g2_broker_state_fresh",
                False,
            ),
        },

        "broker_submission_allowed":
        False,

        "paper_order_submission_allowed":
        False,

        "live_execution_allowed":
        False,

        "automatic_promotion_allowed":
        False,

        "real_money_trading_allowed":
        False,

        "next_gate":
        "REPAIR_PAPER_STATE_RISK_EVIDENCE",
    }


def evaluate_paper_state_risk_preflight(
    g2_proof,
    completion_status,
    shadow_order,
    authorization_result,
    now=None,
    max_g2_age_seconds=DEFAULT_MAX_G2_AGE_SECONDS,
):
    now = (
        _utc_datetime(
            now
        )
        or datetime.now(
            timezone.utc
        )
    )

    input_shapes_valid = all(
        isinstance(
            payload,
            dict,
        )
        for payload in (
            g2_proof,
            completion_status,
            shadow_order,
            authorization_result,
        )
    )

    g2_proof = (
        g2_proof
        if isinstance(
            g2_proof,
            dict,
        )
        else {}
    )
    completion_status = (
        completion_status
        if isinstance(
            completion_status,
            dict,
        )
        else {}
    )
    shadow_order = (
        shadow_order
        if isinstance(
            shadow_order,
            dict,
        )
        else {}
    )
    authorization_result = (
        authorization_result
        if isinstance(
            authorization_result,
            dict,
        )
        else {}
    )

    g2_digest = _digest(
        g2_proof
    )
    completion_digest = _digest(
        completion_status
    )
    shadow_digest = _digest(
        shadow_order
    )

    digests = {
        "g2_paper_read_only_proof_sha256":
        g2_digest,

        "completion_status_sha256":
        completion_digest,

        "shadow_order_sha256":
        shadow_digest,
    }

    if isinstance(
        max_g2_age_seconds,
        bool,
    ):
        configured_max_age = None
    else:
        try:
            configured_max_age = float(
                max_g2_age_seconds
            )
        except (
            TypeError,
            ValueError,
            OverflowError,
        ):
            configured_max_age = None

    risk_policy_valid = (
        configured_max_age
        is not None
        and math.isfinite(
            configured_max_age
        )
        and 0
        <
        configured_max_age
        <=
        DEFAULT_MAX_G2_AGE_SECONDS
    )

    completion_checks = (
        completion_status.get(
            "checks"
        )
        if isinstance(
            completion_status.get(
                "checks"
            ),
            dict,
        )
        else {}
    )
    completion_binding = (
        completion_status.get(
            "evidence_binding"
        )
        if isinstance(
            completion_status.get(
                "evidence_binding"
            ),
            dict,
        )
        else {}
    )

    completion_valid = (
        completion_status.get(
            "status"
        )
        ==
        "PAPER_RUNTIME_VALIDATED_SHADOW_ONLY"
        and completion_status.get(
            "next_gate"
        )
        ==
        "MANUAL_PAPER_ORDER_AUTHORIZATION_NOT_GRANTED"
        and completion_status.get(
            "failure_reasons"
        )
        ==
        []
        and _safe_flags(
            completion_status
        )
        and all(
            completion_checks.get(
                name
            )
            is True
            for name in _REQUIRED_COMPLETION_CHECKS
        )
    )

    completion_g2_bound = (
        g2_digest
        is not None
        and hmac.compare_digest(
            str(
                completion_binding.get(
                    "g2_paper_read_only_proof_sha256"
                )
                or ""
            ).strip().lower(),
            g2_digest,
        )
    )

    completion_shadow_bound = (
        shadow_digest
        is not None
        and hmac.compare_digest(
            str(
                completion_binding.get(
                    "g4_shadow_order_sha256"
                )
                or ""
            ).strip().lower(),
            shadow_digest,
        )
    )

    order_symbol = str(
        shadow_order.get(
            "symbol"
        )
        or ""
    ).strip().upper()
    order_action = str(
        shadow_order.get(
            "action"
        )
        or ""
    ).strip().upper()

    quantity_value = shadow_order.get(
        "quantity"
    )
    quantity = (
        quantity_value
        if type(
            quantity_value
        )
        is int
        and quantity_value
        >
        0
        else None
    )

    limit_price = _safe_number(
        shadow_order.get(
            "limit_price"
        )
    )
    order_notional = _safe_number(
        shadow_order.get(
            "order_notional_usd"
        )
    )

    expected_notional = (
        quantity
        *
        limit_price
        if quantity
        is not None
        and limit_price
        is not None
        else None
    )

    order_shape_valid = (
        _safe_flags(
            shadow_order
        )
        and shadow_order.get(
            "status"
        )
        ==
        "SHADOW_ACCEPTED"
        and str(
            shadow_order.get(
                "asset_type"
            )
            or ""
        ).strip().upper()
        ==
        "STK"
        and order_action
        in {
            "BUY",
            "SELL",
        }
        and str(
            shadow_order.get(
                "order_type"
            )
            or ""
        ).strip().upper()
        ==
        "LIMIT"
        and str(
            shadow_order.get(
                "time_in_force"
            )
            or ""
        ).strip().upper()
        ==
        "DAY"
        and bool(
            order_symbol
        )
        and quantity
        is not None
        and limit_price
        is not None
        and limit_price
        >
        0
        and order_notional
        is not None
        and order_notional
        >
        0
        and expected_notional
        is not None
        and abs(
            order_notional
            -
            expected_notional
        )
        <=
        0.02
    )

    auth_checks = (
        authorization_result.get(
            "checks"
        )
        if isinstance(
            authorization_result.get(
                "checks"
            ),
            dict,
        )
        else {}
    )

    auth_check_contract_valid = (
        set(
            auth_checks
        )
        ==
        _EXPECTED_G5_CHECKS
        and all(
            value
            is True
            for value in auth_checks.values()
        )
    )

    auth_issued = _utc_datetime(
        authorization_result.get(
            "authorization_issued_at"
        )
    )
    auth_expires = _utc_datetime(
        authorization_result.get(
            "authorization_expires_at"
        )
    )

    auth_age = (
        (
            now
            -
            auth_issued
        ).total_seconds()
        if auth_issued
        is not None
        else None
    )
    auth_lifetime = (
        (
            auth_expires
            -
            auth_issued
        ).total_seconds()
        if auth_expires
        is not None
        and auth_issued
        is not None
        else None
    )

    authorization_current = (
        auth_age
        is not None
        and -2
        <=
        auth_age
        <=
        DEFAULT_MAX_AUTH_LIFETIME_SECONDS
        and auth_expires
        is not None
        and auth_expires
        >=
        now
        and auth_lifetime
        is not None
        and 0
        <
        auth_lifetime
        <=
        DEFAULT_MAX_AUTH_LIFETIME_SECONDS
    )

    authorization_valid = (
        authorization_result.get(
            "status"
        )
        ==
        "MANUAL_PAPER_AUTHORIZATION_VALIDATED"
        and authorization_result.get(
            "mode"
        )
        ==
        "PAPER"
        and authorization_result.get(
            "scope"
        )
        ==
        "ONE_PAPER_ORDER"
        and authorization_result.get(
            "next_gate"
        )
        ==
        "PAPER_EXECUTION_CONNECTOR_REVIEW_REQUIRED"
        and authorization_result.get(
            "authorization_can_be_consumed_once"
        )
        is True
        and _uuid4(
            authorization_result.get(
                "authorization_id"
            )
        )
        is not None
        and _safe_flags(
            authorization_result
        )
        and auth_check_contract_valid
    )

    authorization_completion_bound = (
        completion_digest
        is not None
        and hmac.compare_digest(
            str(
                authorization_result.get(
                    "completion_status_sha256"
                )
                or ""
            ).strip().lower(),
            completion_digest,
        )
    )

    authorization_shadow_bound = (
        shadow_digest
        is not None
        and hmac.compare_digest(
            str(
                authorization_result.get(
                    "shadow_order_sha256"
                )
                or ""
            ).strip().lower(),
            shadow_digest,
        )
    )

    run_mode = (
        g2_proof.get(
            "run_mode"
        )
        if isinstance(
            g2_proof.get(
                "run_mode"
            ),
            dict,
        )
        else {}
    )
    snapshot = (
        g2_proof.get(
            "snapshot"
        )
        if isinstance(
            g2_proof.get(
                "snapshot"
            ),
            dict,
        )
        else {}
    )
    readiness = (
        g2_proof.get(
            "readiness"
        )
        if isinstance(
            g2_proof.get(
                "readiness"
            ),
            dict,
        )
        else {}
    )
    attestation = (
        g2_proof.get(
            "gateway_read_only_attestation"
        )
        if isinstance(
            g2_proof.get(
                "gateway_read_only_attestation"
            ),
            dict,
        )
        else {}
    )

    g2_read_only_mode = (
        run_mode.get(
            "mode"
        )
        ==
        "READ_ONLY"
        and run_mode.get(
            "mode_valid"
        )
        is True
        and run_mode.get(
            "read_only"
        )
        is True
        and run_mode.get(
            "paper_order_submission_requested"
        )
        is False
        and run_mode.get(
            "live_execution_allowed"
        )
        is False
    )

    config = (
        snapshot.get(
            "config"
        )
        if isinstance(
            snapshot.get(
                "config"
            ),
            dict,
        )
        else {}
    )
    requests_complete = (
        snapshot.get(
            "requests_complete"
        )
        if isinstance(
            snapshot.get(
                "requests_complete"
            ),
            dict,
        )
        else {}
    )

    g2_snapshot_safe = (
        snapshot.get(
            "status"
        )
        in {
            "CONNECTED",
            "PARTIAL",
        }
        and config.get(
            "mode"
        )
        ==
        "PAPER"
        and config.get(
            "mode_valid"
        )
        is True
        and config.get(
            "endpoint_safe"
        )
        is True
        and config.get(
            "host"
        )
        ==
        "127.0.0.1"
        and config.get(
            "port"
        )
        ==
        4002
        and config.get(
            "read_only"
        )
        is True
        and config.get(
            "live_trading_allowed"
        )
        is False
        and snapshot.get(
            "order_submission_hard_blocked"
        )
        is True
        and snapshot.get(
            "live_trading_allowed"
        )
        is False
        and snapshot.get(
            "gateway_read_only_configuration_independently_attested"
        )
        is True
        and all(
            requests_complete.get(
                name
            )
            is True
            for name in (
                "managed_accounts",
                "account_summary",
                "positions",
                "open_orders",
            )
        )
    )

    required_checks = (
        readiness.get(
            "checks"
        )
        if isinstance(
            readiness.get(
                "checks"
            ),
            list,
        )
        else []
    )

    g2_required_checks_valid = (
        bool(
            required_checks
        )
        and all(
            isinstance(
                item,
                dict,
            )
            and isinstance(
                item.get(
                    "check"
                ),
                str,
            )
            and isinstance(
                item.get(
                    "required"
                ),
                bool,
            )
            and isinstance(
                item.get(
                    "passed"
                ),
                bool,
            )
            for item in required_checks
        )
        and all(
            item.get(
                "passed"
            )
            is True
            for item in required_checks
            if item.get(
                "required"
            )
            is True
        )
    )

    g2_readiness_ready = (
        readiness.get(
            "readiness"
        )
        ==
        "READY_FOR_PAPER_READ_ONLY"
        and readiness.get(
            "required_failure_count"
        )
        ==
        0
        and readiness.get(
            "paper_order_submission_allowed"
        )
        is False
        and readiness.get(
            "live_execution_allowed"
        )
        is False
        and readiness.get(
            "gateway_read_only_configuration_independently_attested"
        )
        is True
        and g2_required_checks_valid
    )

    g2_attestation_verified = (
        attestation.get(
            "status"
        )
        ==
        "VERIFIED"
        and attestation.get(
            "verified"
        )
        is True
        and attestation.get(
            "gateway_read_only_configuration_independently_attested"
        )
        is True
        and attestation.get(
            "failure_reasons"
        )
        ==
        []
        and _safe_flags(
            attestation
        )
    )

    snapshot_age = _age_seconds(
        snapshot.get(
            "timestamp"
        ),
        now,
    )
    readiness_age = _age_seconds(
        readiness.get(
            "timestamp"
        ),
        now,
    )

    g2_broker_state_fresh = (
        risk_policy_valid
        and snapshot_age
        is not None
        and readiness_age
        is not None
        and snapshot_age
        <=
        configured_max_age
        and readiness_age
        <=
        configured_max_age
    )

    evidence_run_id = _uuid4(
        g2_proof.get(
            "evidence_run_id"
        )
    )

    positions = snapshot.get(
        "positions"
    )
    open_orders = snapshot.get(
        "open_orders"
    )

    positions_valid = (
        isinstance(
            positions,
            list,
        )
        and all(
            isinstance(
                row,
                dict,
            )
            and isinstance(
                row.get(
                    "symbol"
                ),
                str,
            )
            and bool(
                row.get(
                    "symbol"
                ).strip()
            )
            and _safe_number(
                row.get(
                    "position"
                )
            )
            is not None
            for row in positions
        )
    )

    open_orders_valid = (
        isinstance(
            open_orders,
            list,
        )
        and all(
            isinstance(
                row,
                dict,
            )
            and type(
                row.get(
                    "order_id"
                )
            )
            is int
            and row.get(
                "order_id"
            )
            >=
            0
            and isinstance(
                row.get(
                    "symbol"
                ),
                str,
            )
            and bool(
                row.get(
                    "symbol"
                ).strip()
            )
            and str(
                row.get(
                    "action"
                )
                or ""
            ).strip().upper()
            in {
                "BUY",
                "SELL",
            }
            and _safe_number(
                row.get(
                    "quantity"
                )
            )
            is not None
            and _safe_number(
                row.get(
                    "quantity"
                )
            )
            >
            0
            for row in open_orders
        )
    )

    broker_position_qty = 0.0
    relevant_position_type_valid = True

    if positions_valid:
        for row in positions:
            if str(
                row.get(
                    "symbol"
                )
                or ""
            ).strip().upper() != order_symbol:
                continue

            security_type = str(
                row.get(
                    "security_type"
                )
                or ""
            ).strip().upper()

            if security_type != "STK":
                relevant_position_type_valid = False
                continue

            broker_position_qty += _safe_number(
                row.get(
                    "position"
                )
            )

    open_sell_qty = 0.0
    relevant_open_order_type_valid = True

    if open_orders_valid:
        for row in open_orders:
            if str(
                row.get(
                    "symbol"
                )
                or ""
            ).strip().upper() != order_symbol:
                continue

            security_type = str(
                row.get(
                    "security_type"
                )
                or ""
            ).strip().upper()

            if security_type != "STK":
                relevant_open_order_type_valid = False
                continue

            if str(
                row.get(
                    "action"
                )
                or ""
            ).strip().upper() == "SELL":
                open_sell_qty += _safe_number(
                    row.get(
                        "quantity"
                    )
                )

    account_metrics = (
        readiness.get(
            "account_metrics"
        )
        if isinstance(
            readiness.get(
                "account_metrics"
            ),
            dict,
        )
        else {}
    )
    available_funds = _safe_number(
        account_metrics.get(
            "available_funds"
        )
    )

    account_summary = (
        snapshot.get(
            "account_summary"
        )
        if isinstance(
            snapshot.get(
                "account_summary"
            ),
            dict,
        )
        else {}
    )
    raw_available_funds = (
        account_summary.get(
            "AvailableFunds"
        )
        if isinstance(
            account_summary.get(
                "AvailableFunds"
            ),
            dict,
        )
        else {}
    )
    snapshot_available_funds = _safe_number(
        raw_available_funds.get(
            "value"
        )
    )

    available_funds_cross_checked = (
        available_funds
        is not None
        and available_funds
        >=
        0
        and snapshot_available_funds
        is not None
        and snapshot_available_funds
        >=
        0
        and abs(
            available_funds
            -
            snapshot_available_funds
        )
        <=
        1e-6
    )

    broker_state_payload_valid = (
        positions_valid
        and open_orders_valid
        and relevant_position_type_valid
        and relevant_open_order_type_valid
        and available_funds_cross_checked
    )

    buy_available_funds_sufficient = (
        order_action
        !=
        "BUY"
        or (
            order_notional
            is not None
            and available_funds_cross_checked
            and available_funds
            >=
            order_notional
        )
    )

    sell_inventory_sufficient = (
        order_action
        !=
        "SELL"
        or (
            quantity
            is not None
            and positions_valid
            and open_orders_valid
            and relevant_position_type_valid
            and relevant_open_order_type_valid
            and max(
                broker_position_qty,
                0.0,
            )
            -
            open_sell_qty
            >=
            quantity
        )
    )

    checks = {
        "input_shapes_valid":
        input_shapes_valid,

        "risk_policy_valid":
        risk_policy_valid,

        "completion_validated":
        completion_valid,

        "completion_g2_digest_bound":
        completion_g2_bound,

        "completion_shadow_digest_bound":
        completion_shadow_bound,

        "shadow_order_shape_valid":
        order_shape_valid,

        "authorization_validated":
        authorization_valid,

        "authorization_current":
        authorization_current,

        "authorization_completion_digest_bound":
        authorization_completion_bound,

        "authorization_shadow_digest_bound":
        authorization_shadow_bound,

        "g2_evidence_run_id_valid":
        evidence_run_id
        is not None,

        "g2_read_only_mode":
        g2_read_only_mode,

        "g2_snapshot_safe":
        g2_snapshot_safe,

        "g2_readiness_ready":
        g2_readiness_ready,

        "g2_attestation_verified":
        g2_attestation_verified,

        "g2_broker_state_fresh":
        g2_broker_state_fresh,

        "broker_state_payload_valid":
        broker_state_payload_valid,

        "buy_available_funds_sufficient":
        buy_available_funds_sufficient,

        "sell_inventory_sufficient":
        sell_inventory_sufficient,
    }

    failures = [
        name
        for name, passed in checks.items()
        if passed
        is not True
    ]

    if failures:
        return _blocked(
            checks,
            failures,
            digests,
        )

    return {
        "engine":
        ENGINE_VERSION,

        "generated_at":
        now.isoformat(),

        "status":
        "PAPER_STATE_RISK_VALIDATED_NON_EXECUTABLE",

        "checks":
        checks,

        "failure_reasons":
        [],

        "evidence_binding":
        digests,

        "authorization_id":
        authorization_result.get(
            "authorization_id"
        ),

        "risk_summary": {
            "action":
            order_action,

            "symbol":
            order_symbol,

            "buy_available_funds_sufficient":
            buy_available_funds_sufficient,

            "sell_inventory_sufficient":
            sell_inventory_sufficient,

            "broker_state_fresh":
            True,
        },

        "broker_submission_allowed":
        False,

        "paper_order_submission_allowed":
        False,

        "live_execution_allowed":
        False,

        "automatic_promotion_allowed":
        False,

        "real_money_trading_allowed":
        False,

        "next_gate":
        "ATOMIC_AUTHORIZATION_RESERVATION_REVIEW_REQUIRED",
    }
