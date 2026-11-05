"""G7.17 fail-closed Paper broker-state risk preflight.

The authorized G2 proof remains the provenance bound into G0-G4 completion.
A second post-authorization G2 read-only proof supplies fresh broker state.
The two proofs must share the exact independently verified attestation and the
same verified Paper account identity.

This module never submits, reserves, stages, or constructs a broker order.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import hmac
import json
import math
from uuid import UUID

from engines.ibkr_paper_readiness_engine import (
    ACTIVE_OPEN_ORDER_STATUSES,
    open_order_execution_evidence_is_consistent,
    open_order_payload_is_valid,
    open_order_status_evidence_is_consistent,
)


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

_REQUIRED_G7_POSITION_CHECKS = (
    "positions_snapshot_complete",
    "positions_payload_valid",
    "position_accounts_match_verified_paper_accounts",
    "portfolio_quantities_and_symbols_valid",
    "position_instruments_unambiguous",
    "open_order_identifiers_unique",
    "open_order_statuses_active",
    "execution_snapshot_complete",
    "open_order_execution_evidence_consistent",
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


def _verified_account_fingerprints(snapshot):
    if not isinstance(
        snapshot,
        dict,
    ):
        return ()

    guard = snapshot.get(
        "paper_account_guard"
    )

    if not isinstance(
        guard,
        dict,
    ):
        return ()

    if guard.get(
        "paper_account_verified"
    ) is not True:
        return ()

    values = guard.get(
        "verified_account_fingerprints"
    )

    if not isinstance(
        values,
        list,
    ):
        return ()

    fingerprints = tuple(
        str(
            value
        ).strip()
        for value in values
    )

    canonical = tuple(
        sorted(
            set(
                fingerprints
            )
        )
    )

    if (
        len(
            fingerprints
        )
        !=
        1
        or fingerprints
        !=
        canonical
    ):
        return ()

    if any(
        len(
            value
        )
        !=
        15
        or not value.startswith(
            "IBKR-"
        )
        or any(
            character
            not in
            "0123456789ABCDEF"
            for character in value[
                5:
            ]
        )
        for value in fingerprints
    ):
        return ()

    summary_fingerprints = snapshot.get(
        "account_summary_account_fingerprints"
    )

    if (
        not isinstance(
            summary_fingerprints,
            list,
        )
        or tuple(
            summary_fingerprints
        )
        !=
        fingerprints
    ):
        return ()

    return fingerprints


def _g2_parts(g2_proof):
    if not isinstance(
        g2_proof,
        dict,
    ):
        g2_proof = {}

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

    return (
        run_mode,
        snapshot,
        readiness,
        attestation,
    )


def _g2_contract(
    g2_proof,
):
    (
        run_mode,
        snapshot,
        readiness,
        attestation,
    ) = _g2_parts(
        g2_proof
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

    run_mode_valid = (
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

    snapshot_safe = (
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

    readiness_checks = (
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

    required_checks_valid = (
        bool(
            readiness_checks
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
            for item in readiness_checks
        )
        and all(
            item.get(
                "passed"
            )
            is True
            for item in readiness_checks
            if item.get(
                "required"
            )
            is True
        )
        and all(
            sum(
                1 for item in readiness_checks
                if item.get("check") == name
                and item.get("required") is True
                and item.get("passed") is True
            ) == 1
            for name in _REQUIRED_G7_POSITION_CHECKS
        )
    )

    readiness_ready = (
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
        and required_checks_valid
    )

    attestation_verified = (
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

    fingerprints = _verified_account_fingerprints(
        snapshot
    )

    return {
        "run_mode":
        run_mode,

        "snapshot":
        snapshot,

        "readiness":
        readiness,

        "attestation":
        attestation,

        "run_mode_valid":
        run_mode_valid,

        "snapshot_safe":
        snapshot_safe,

        "readiness_ready":
        readiness_ready,

        "attestation_verified":
        attestation_verified,

        "account_fingerprints":
        fingerprints,

        "post_review_probe_stage":
        g2_proof.get("probe_stage")
        ==
        "POST_REVIEW_PROBE",

        "evidence_run_id_valid":
        _uuid4(
            g2_proof.get(
                "evidence_run_id"
            )
        )
        is not None,
    }


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
            checks.get(
                "buy_available_funds_sufficient"
            ),

            "sell_inventory_sufficient":
            checks.get(
                "sell_inventory_sufficient"
            ),

            "broker_state_fresh":
            checks.get(
                "fresh_g2_broker_state_fresh",
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
    authorized_g2_proof,
    fresh_g2_proof,
    completion_status,
    shadow_order,
    authorization_result,
    now=None,
    max_g2_age_seconds=DEFAULT_MAX_G2_AGE_SECONDS,
):
    if now is None:
        now_utc = datetime.now(
            timezone.utc
        )
        reference_clock_valid = True
    else:
        now_utc = _utc_datetime(
            now
        )
        reference_clock_valid = (
            now_utc
            is not None
        )

        if now_utc is None:
            now_utc = datetime.now(
                timezone.utc
            )

    now = now_utc

    input_shapes_valid = all(
        isinstance(
            payload,
            dict,
        )
        for payload in (
            authorized_g2_proof,
            fresh_g2_proof,
            completion_status,
            shadow_order,
            authorization_result,
        )
    )

    authorized_g2_proof = (
        authorized_g2_proof
        if isinstance(
            authorized_g2_proof,
            dict,
        )
        else {}
    )
    fresh_g2_proof = (
        fresh_g2_proof
        if isinstance(
            fresh_g2_proof,
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

    authorized_g2_digest = _digest(
        authorized_g2_proof
    )
    fresh_g2_digest = _digest(
        fresh_g2_proof
    )
    completion_digest = _digest(
        completion_status
    )
    shadow_digest = _digest(
        shadow_order
    )

    digests = {
        "authorized_g2_paper_read_only_proof_sha256":
        authorized_g2_digest,

        "fresh_g2_paper_read_only_proof_sha256":
        fresh_g2_digest,

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

    completion_authorized_g2_bound = (
        authorized_g2_digest
        is not None
        and hmac.compare_digest(
            str(
                completion_binding.get(
                    "g2_paper_read_only_proof_sha256"
                )
                or ""
            ).strip().lower(),
            authorized_g2_digest,
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

    authorized_contract = _g2_contract(
        authorized_g2_proof
    )
    fresh_contract = _g2_contract(
        fresh_g2_proof
    )

    authorized_g2_contract_valid = all(
        (
            authorized_contract[
                "run_mode_valid"
            ],
            authorized_contract[
                "snapshot_safe"
            ],
            authorized_contract[
                "readiness_ready"
            ],
            authorized_contract[
                "attestation_verified"
            ],
            authorized_contract[
                "evidence_run_id_valid"
            ],
            authorized_contract[
                "post_review_probe_stage"
            ],
            bool(
                authorized_contract[
                    "account_fingerprints"
                ]
            ),
        )
    )

    fresh_g2_contract_valid = all(
        (
            fresh_contract[
                "run_mode_valid"
            ],
            fresh_contract[
                "snapshot_safe"
            ],
            fresh_contract[
                "readiness_ready"
            ],
            fresh_contract[
                "attestation_verified"
            ],
            fresh_contract[
                "evidence_run_id_valid"
            ],
            fresh_contract[
                "post_review_probe_stage"
            ],
            bool(
                fresh_contract[
                    "account_fingerprints"
                ]
            ),
        )
    )

    authorized_attestation_digest = _digest(
        authorized_contract[
            "attestation"
        ]
    )
    fresh_attestation_digest = _digest(
        fresh_contract[
            "attestation"
        ]
    )

    fresh_identity_matches_authorized = (
        authorized_attestation_digest
        is not None
        and fresh_attestation_digest
        is not None
        and hmac.compare_digest(
            authorized_attestation_digest,
            fresh_attestation_digest,
        )
        and authorized_contract[
            "account_fingerprints"
        ]
        ==
        fresh_contract[
            "account_fingerprints"
        ]
    )

    fresh_snapshot = fresh_contract[
        "snapshot"
    ]
    fresh_readiness = fresh_contract[
        "readiness"
    ]

    fresh_snapshot_timestamp = _utc_datetime(
        fresh_snapshot.get(
            "timestamp"
        )
    )
    fresh_snapshot_completed_at = _utc_datetime(
        fresh_snapshot.get(
            "snapshot_completed_at_utc"
        )
    )
    fresh_readiness_timestamp = _utc_datetime(
        fresh_readiness.get(
            "timestamp"
        )
    )

    fresh_snapshot_age = _age_seconds(
        fresh_snapshot.get(
            "timestamp"
        ),
        now,
    )
    fresh_snapshot_completion_age = _age_seconds(
        fresh_snapshot.get(
            "snapshot_completed_at_utc"
        ),
        now,
    )
    fresh_readiness_age = _age_seconds(
        fresh_readiness.get(
            "timestamp"
        ),
        now,
    )

    fresh_g2_broker_state_fresh = (
        risk_policy_valid
        and fresh_snapshot_age
        is not None
        and fresh_snapshot_completion_age
        is not None
        and fresh_readiness_age
        is not None
        and fresh_snapshot_age
        <=
        configured_max_age
        and fresh_snapshot_completion_age
        <=
        configured_max_age
        and fresh_readiness_age
        <=
        configured_max_age
        and fresh_snapshot_completed_at
        is not None
        and fresh_snapshot_timestamp
        is not None
        and fresh_snapshot_timestamp
        <=
        fresh_snapshot_completed_at
        <=
        fresh_readiness_timestamp
    )

    fresh_g2_post_authorization = (
        auth_issued
        is not None
        and fresh_snapshot_timestamp
        is not None
        and fresh_snapshot_completed_at
        is not None
        and fresh_readiness_timestamp
        is not None
        and (
            fresh_snapshot_timestamp
            -
            auth_issued
        ).total_seconds()
        >=
        -2
        and (
            fresh_snapshot_completed_at
            -
            auth_issued
        ).total_seconds()
        >=
        -2
        and (
            fresh_readiness_timestamp
            -
            auth_issued
        ).total_seconds()
        >=
        -2
    )

    positions = fresh_snapshot.get(
        "positions"
    )
    open_orders = fresh_snapshot.get(
        "open_orders"
    )
    fresh_account_fingerprints = set(
        fresh_contract[
            "account_fingerprints"
        ]
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
            and isinstance(
                row.get(
                    "account"
                ),
                str,
            )
            and row.get(
                "account"
            )
            in fresh_account_fingerprints
            for row in positions
        )
    )

    # Match the stricter main-branch G7 position identity contract.
    # Never aggregate multiple contracts or currencies under one ticker.
    position_identity_valid = (
        positions_valid
        and all(
            row.get("security_type") == "STK"
            and row.get("currency") == "USD"
            and type(row.get("con_id")) is int
            and row["con_id"] > 0
            for row in positions
        )
        and len({
            row["symbol"].strip().upper()
            for row in positions
        }) == len(positions)
        and len({
            row["con_id"]
            for row in positions
        }) == len(positions)
    )

    open_orders_valid = (
        open_order_payload_is_valid(
            open_orders
        )
        and all(
            isinstance(
                row.get(
                    "account"
                ),
                str,
            )
            and row.get(
                "account"
            )
            in fresh_account_fingerprints
            for row in open_orders
        )
    )

    open_order_identifiers_unique = (
        open_orders_valid
        and len({
            row["perm_id"]
            for row in open_orders
        })
        ==
        len(
            open_orders
        )
        and len({
            (row["client_id"], row["order_id"])
            for row in open_orders
        })
        ==
        len(open_orders)
    )

    open_order_statuses_active = (
        open_orders_valid
        and all(
            type(row.get("status")) is str
            and row["status"] in ACTIVE_OPEN_ORDER_STATUSES
            for row in open_orders
        )
        and open_order_status_evidence_is_consistent(
            open_orders,
            fresh_snapshot.get("order_status"),
        )
    )

    open_order_execution_evidence_consistent = (
        open_order_statuses_active
        and open_order_execution_evidence_is_consistent(
            open_orders,
            fresh_snapshot.get("order_status"),
            fresh_snapshot.get("executions"),
            fresh_snapshot.get("snapshot_completed_at_utc"),
        )
    )

    # Open orders are broker contract identities, not just tickers.
    # A same-symbol option or a different stock conId must never consume
    # (or validate) inventory for the reviewed stock order.
    same_symbol_position_con_ids = (
        {
            row["con_id"]
            for row in positions
            if row["symbol"].strip().upper() == order_symbol
        }
        if position_identity_valid else set()
    )
    relevant_open_orders_match_position = (
        open_orders_valid
        and (
            order_action != "SELL"
            or all(
                row["con_id"] in same_symbol_position_con_ids
                for row in open_orders
                if row["symbol"].strip().upper() == order_symbol
            )
        )
    )

    broker_position_qty = 0.0
    relevant_position_type_valid = True

    if position_identity_valid:
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
        fresh_readiness.get(
            "account_metrics"
        )
        if isinstance(
            fresh_readiness.get(
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
        fresh_snapshot.get(
            "account_summary"
        )
        if isinstance(
            fresh_snapshot.get(
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
    available_funds_currency = str(
        raw_available_funds.get(
            "currency"
        )
        or ""
    ).strip().upper()

    available_funds_cross_checked = (
        available_funds_currency
        ==
        "USD"
        and available_funds
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
        position_identity_valid
        and open_orders_valid
        and open_order_identifiers_unique
        and open_order_statuses_active
        and open_order_execution_evidence_consistent
        and relevant_position_type_valid
        and relevant_open_order_type_valid
        and relevant_open_orders_match_position
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
            and position_identity_valid
            and open_orders_valid
            and open_order_statuses_active
            and open_order_execution_evidence_consistent
            and relevant_position_type_valid
            and relevant_open_order_type_valid
            and relevant_open_orders_match_position
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

        "reference_clock_valid":
        reference_clock_valid,

        "risk_policy_valid":
        risk_policy_valid,

        "completion_validated":
        completion_valid,

        "completion_authorized_g2_digest_bound":
        completion_authorized_g2_bound,

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

        "authorized_g2_contract_valid":
        authorized_g2_contract_valid,

        "fresh_g2_contract_valid":
        fresh_g2_contract_valid,

        "fresh_g2_identity_matches_authorized":
        fresh_identity_matches_authorized,

        "fresh_g2_broker_state_fresh":
        fresh_g2_broker_state_fresh,

        "fresh_g2_post_authorization":
        fresh_g2_post_authorization,

        "broker_state_payload_valid":
        broker_state_payload_valid,

        "open_order_identifiers_unique":
        open_order_identifiers_unique,

        "open_order_statuses_active":
        open_order_statuses_active,

        "open_order_execution_evidence_consistent":
        open_order_execution_evidence_consistent,

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
