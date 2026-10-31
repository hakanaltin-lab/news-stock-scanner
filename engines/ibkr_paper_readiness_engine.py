"""
V8.9.4 AURORA IBKR Paper Readiness Safety Gate

Purpose:
- Validate whether the broker connection is safe enough for paper execution work
- Compare broker positions with AURORA's static portfolio input
- Keep LIVE execution blocked
- Fail closed on missing account/cash/position information

This engine does not place orders.
"""

from datetime import datetime, timezone


ENGINE_VERSION = (
    "V8.9.5 IBKR Paper Readiness Safety Gate"
)


def safe_float(
    value,
    default=None
):
    try:
        return float(
            value
        )
    except (
        TypeError,
        ValueError
    ):
        return default


def account_metric(
    snapshot,
    name
):
    value = (
        (
            snapshot.get(
                "account_summary",
                {}
            )
            or
            {}
        ).get(
            name,
            {}
        )
        or
        {}
    ).get(
        "value"
    )

    return safe_float(
        value,
        None
    )


def normalize_expected_positions(
    portfolio_rows
):
    expected = {}

    for row in portfolio_rows:
        ticker = str(
            row.get(
                "ticker",
                ""
            )
        ).strip().upper()

        if not ticker:
            continue

        shares = safe_float(
            row.get(
                "shares"
            ),
            0.0
        )

        expected[
            ticker
        ] = shares

    return expected


def normalize_broker_positions(
    snapshot
):
    broker = {}

    for row in (
        snapshot.get(
            "positions",
            []
        )
        or
        []
    ):
        ticker = str(
            row.get(
                "symbol",
                ""
            )
        ).strip().upper()

        if not ticker:
            continue

        position = safe_float(
            row.get(
                "position"
            ),
            0.0
        )

        if abs(
            position
        ) < 1e-9:
            continue

        broker[
            ticker
        ] = (
            broker.get(
                ticker,
                0.0
            )
            +
            position
        )

    return broker


def compare_positions(
    portfolio_rows,
    snapshot
):
    expected = (
        normalize_expected_positions(
            portfolio_rows
        )
    )

    broker = (
        normalize_broker_positions(
            snapshot
        )
    )

    symbols = sorted(
        set(
            expected
        )
        |
        set(
            broker
        )
    )

    rows = []

    mismatch_count = 0

    for ticker in symbols:
        expected_shares = (
            expected.get(
                ticker,
                0.0
            )
        )

        broker_shares = (
            broker.get(
                ticker,
                0.0
            )
        )

        difference = (
            broker_shares
            -
            expected_shares
        )

        matched = (
            abs(
                difference
            )
            <
            1e-6
        )

        if not matched:
            mismatch_count += 1

        rows.append({
            "ticker":
            ticker,

            "aurora_shares":
            round(
                expected_shares,
                6
            ),

            "broker_shares":
            round(
                broker_shares,
                6
            ),

            "difference":
            round(
                difference,
                6
            ),

            "matched":
            matched
        })

    return {
        "expected_position_count":
        len(
            expected
        ),

        "broker_position_count":
        len(
            broker
        ),

        "mismatch_count":
        mismatch_count,

        "all_positions_match":
        mismatch_count
        ==
        0,

        "rows":
        rows
    }


def evaluate_ibkr_paper_readiness(
    broker_snapshot,
    portfolio_rows
):
    broker_snapshot = (
        broker_snapshot
        or
        {}
    )

    status = broker_snapshot.get(
        "status"
    )

    config = (
        broker_snapshot.get(
            "config",
            {}
        )
        or
        {}
    )

    checks = []

    def add_check(
        name,
        passed,
        required,
        detail
    ):
        checks.append({
            "check":
            name,

            "passed":
            bool(
                passed
            ),

            "required":
            bool(
                required
            ),

            "detail":
            detail
        })

    add_check(
        "paper_mode_only",
        (
            config.get(
                "mode"
            )
            ==
            "PAPER"
            and
            config.get(
                "mode_valid"
            )
            is True
        ),
        True,
        (
            "Connector must run in explicitly configured PAPER mode."
        )
    )


    add_check(
        "safe_loopback_paper_endpoint",
        config.get("endpoint_safe") is True,
        True,
        (
            "IBKR access must be restricted to 127.0.0.1:4002."
        )
    )

    paper_account_guard = (
        broker_snapshot.get(
            "paper_account_guard",
            {}
        )
        or
        {}
    )

    add_check(
        "paper_account_allowlist_configured",
        paper_account_guard.get(
            "allowlist_configured"
        )
        is True,
        True,
        (
            "A paper-account allowlist must be configured outside GitHub."
        )
    )

    add_check(
        "paper_account_identity_verified",
        paper_account_guard.get(
            "paper_account_verified"
        )
        is True,
        True,
        (
            "Every managed account returned by IBKR must match the paper allowlist."
        )
    )

    verified_account_fingerprints = sorted({
        str(item).strip()
        for item in (
            paper_account_guard.get(
                "verified_account_fingerprints",
                []
            )
            or
            []
        )
        if str(item).strip()
    })

    account_summary_account_fingerprints = sorted({
        str(item).strip()
        for item in (
            broker_snapshot.get(
                "account_summary_account_fingerprints",
                []
            )
            or
            []
        )
        if str(item).strip()
    })

    add_check(
        "account_summary_accounts_match_managed_accounts",
        (
            bool(
                verified_account_fingerprints
            )
            and
            account_summary_account_fingerprints
            ==
            verified_account_fingerprints
        ),
        True,
        (
            "Account-summary metrics must belong to the exact verified "
            "managed Paper account set."
        )
    )

    add_check(
        "connector_read_only",
        config.get(
            "read_only"
        )
        is True,
        True,
        (
            "The broker snapshot connector must be read-only."
        )
    )

    add_check(
        "order_submission_hard_blocked",
        broker_snapshot.get(
            "order_submission_hard_blocked"
        )
        is True,
        True,
        (
            "The connector must hard-block every placeOrder call."
        )
    )

    add_check(
        "live_trading_hard_blocked",
        broker_snapshot.get(
            "live_trading_allowed"
        )
        is False,
        True,
        (
            "LIVE trading must remain hard-blocked."
        )
    )

    add_check(
        "official_ibapi_available",
        broker_snapshot.get(
            "official_ibapi_available"
        )
        is True,
        True,
        (
            "Official IBKR TWS Python API must be installed on the Gateway VPS."
        )
    )

    add_check(
        "gateway_connected",
        status
        in {
            "CONNECTED",
            "PARTIAL"
        },
        True,
        (
            "IB Gateway must accept the socket connection."
        )
    )

    account_count = safe_float(
        broker_snapshot.get(
            "account_count"
        ),
        0
    )

    add_check(
        "managed_account_received",
        account_count
        >=
        1,
        True,
        (
            "At least one paper managed account must be returned."
        )
    )

    add_check(
        "single_managed_account_for_readiness",
        account_count
        ==
        1,
        True,
        (
            "Read-only readiness currently supports exactly one managed "
            "Paper account because account-summary metrics are not yet "
            "represented per account."
        )
    )

    net_liquidation = account_metric(
        broker_snapshot,
        "NetLiquidation"
    )

    total_cash = account_metric(
        broker_snapshot,
        "TotalCashValue"
    )

    available_funds = account_metric(
        broker_snapshot,
        "AvailableFunds"
    )

    buying_power = account_metric(
        broker_snapshot,
        "BuyingPower"
    )

    add_check(
        "net_liquidation_available",
        net_liquidation
        is not None
        and
        net_liquidation
        >=
        0,
        True,
        (
            "NetLiquidation must be available before execution work."
        )
    )

    add_check(
        "cash_available",
        total_cash
        is not None,
        True,
        (
            "TotalCashValue must be available before execution work."
        )
    )

    add_check(
        "available_funds_available",
        available_funds
        is not None,
        True,
        (
            "AvailableFunds must be available before execution work."
        )
    )

    add_check(
        "buying_power_available",
        buying_power
        is not None,
        False,
        (
            "BuyingPower is useful for validation but is not required "
            "for the first read-only milestone."
        )
    )

    requests_complete = (
        broker_snapshot.get(
            "requests_complete",
            {}
        )
        or
        {}
    )

    add_check(
        "managed_accounts_snapshot_complete",
        requests_complete.get(
            "managed_accounts"
        )
        is True,
        True,
        (
            "Managed-account request must complete."
        )
    )

    add_check(
        "account_summary_snapshot_complete",
        requests_complete.get("account_summary") is True,
        True,
        "Account summary request must finish before read-only readiness.",
    )

    add_check(
        "positions_snapshot_complete",
        requests_complete.get(
            "positions"
        )
        is True,
        True,
        (
            "Position request must complete."
        )
    )

    add_check(
        "open_orders_snapshot_complete",
        requests_complete.get(
            "open_orders"
        )
        is True,
        True,
        (
            "Open-order request must complete."
        )
    )

    positions = broker_snapshot.get("positions", []) or []
    position_accounts_verified = (
        isinstance(positions, list)
        and all(
            isinstance(row, dict)
            and isinstance(row.get("account"), str)
            and row["account"] in verified_account_fingerprints
            for row in positions
        )
    )
    add_check(
        "position_accounts_match_verified_paper_accounts",
        position_accounts_verified,
        True,
        "Every reported position must originate from a verified Paper account.",
    )

    position_sync = compare_positions(
        portfolio_rows,
        broker_snapshot
    )

    add_check(
        "portfolio_sync_observed",
        position_sync.get(
            "broker_position_count",
            0
        )
        >=
        0,
        False,
        (
            "Paper account positions are compared with AURORA CSV. "
            "A mismatch is diagnostic at the read-only stage."
        )
    )

    required_failures = [
        item
        for item in checks
        if (
            item.get(
                "required"
            )
            and
            not item.get(
                "passed"
            )
        )
    ]

    if status == "DISABLED":
        readiness = (
            "DISABLED"
        )

    elif required_failures:
        readiness = (
            "NOT_READY"
        )

    else:
        readiness = (
            "READY_FOR_PAPER_READ_ONLY"
        )

    return {
        "engine":
        ENGINE_VERSION,

        "timestamp":
        datetime.now(
            timezone.utc
        ).isoformat(),

        "readiness":
        readiness,

        "live_execution_allowed":
        False,

        "paper_order_submission_allowed":
        False,

        "required_failure_count":
        len(
            required_failures
        ),

        "checks":
        checks,

        "account_metrics": {
            "net_liquidation":
            net_liquidation,

            "total_cash_value":
            total_cash,

            "available_funds":
            available_funds,

            "buying_power":
            buying_power
        },

        "position_sync":
        position_sync,

        "next_milestone":
        (
            "PAPER_ORDER_DRY_RUN"
            if readiness
            ==
            "READY_FOR_PAPER_READ_ONLY"
            else
            "ESTABLISH_PAPER_READ_ONLY_CONNECTION"
        )
    }
