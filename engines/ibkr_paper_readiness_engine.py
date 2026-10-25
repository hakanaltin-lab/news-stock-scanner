"""
V8.3 AURORA IBKR Paper Readiness Safety Gate

Purpose:
- Validate whether the broker connection is safe enough for paper execution work
- Compare broker positions with AURORA's static portfolio input
- Keep LIVE execution blocked
- Fail closed on missing account/cash/position information

This engine does not place orders.
"""

from datetime import datetime, timezone


ENGINE_VERSION = (
    "V8.3 IBKR Paper Readiness Safety Gate"
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
        config.get(
            "mode"
        )
        ==
        "PAPER",
        True,
        (
            "Connector must run in PAPER mode."
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
