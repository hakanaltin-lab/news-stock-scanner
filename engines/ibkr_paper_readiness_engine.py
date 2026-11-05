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
import math


ENGINE_VERSION = (
    "V8.9.5 IBKR Paper Readiness Safety Gate"
)

ACTIVE_OPEN_ORDER_STATUSES = frozenset({
    "ApiPending",
    "PendingSubmit",
    "PreSubmitted",
    "Submitted",
    "PendingCancel",
})

EXECUTIONS_REQUEST_ID = 8302


def safe_float(
    value,
    default=None
):
    if isinstance(
        value,
        bool
    ):
        return default

    try:
        parsed = float(
            value
        )
    except (
        TypeError,
        ValueError,
        OverflowError
    ):
        return default

    if not math.isfinite(
        parsed
    ):
        return default

    return parsed


def execution_correction_family(execution_id):
    """Return the stable IBKR execution ID prefix shared by corrections."""
    if not isinstance(execution_id, str):
        return None

    normalized = execution_id.strip()
    if not normalized:
        return None

    prefix, separator, revision = normalized.rpartition(".")
    if separator and prefix and revision.isdigit():
        return prefix

    return normalized


def open_order_payload_is_valid(open_orders):
    """Validate the complete stock-order identity needed by risk gates."""
    if not isinstance(open_orders, list):
        return False

    symbol_to_con_id = {}
    con_id_to_symbol = {}

    for row in open_orders:
        if not isinstance(row, dict):
            return False

        symbol = row.get("symbol")
        con_id = row.get("con_id")
        quantity = row.get("quantity")
        if (
            type(row.get("order_id")) is not int
            or row["order_id"] < 0
            or type(row.get("perm_id")) is not int
            or row["perm_id"] <= 0
            or type(row.get("client_id")) is not int
            or row["client_id"] < 0
            or not isinstance(symbol, str)
            or not symbol.strip()
            or row.get("security_type") != "STK"
            or row.get("currency") != "USD"
            or type(con_id) is not int
            or con_id <= 0
            or str(row.get("action") or "").strip().upper()
            not in {"BUY", "SELL"}
            or type(quantity) not in {int, float}
            or safe_float(quantity, None) is None
            or safe_float(quantity, None) <= 0
        ):
            return False

        symbol = symbol.strip().upper()
        if (
            symbol in symbol_to_con_id
            and symbol_to_con_id[symbol] != con_id
        ):
            return False
        if (
            con_id in con_id_to_symbol
            and con_id_to_symbol[con_id] != symbol
        ):
            return False

        symbol_to_con_id[symbol] = con_id
        con_id_to_symbol[con_id] = symbol

    return True


def open_order_status_evidence_is_consistent(
    open_orders,
    order_status_rows,
):
    """Reconcile the two IBKR callbacks that describe each open order."""
    if not isinstance(open_orders, list):
        return False

    if not open_orders:
        return order_status_rows in (None, [])

    if not isinstance(order_status_rows, list) or not order_status_rows:
        return False

    open_orders_by_identity = {}
    for order in open_orders:
        if not isinstance(order, dict):
            return False
        order_id = order.get("order_id")
        perm_id = order.get("perm_id")
        client_id = order.get("client_id")
        quantity = safe_float(order.get("quantity"), None)
        if (
            type(order_id) is not int
            or order_id < 0
            or type(perm_id) is not int
            or perm_id <= 0
            or type(client_id) is not int
            or client_id < 0
            or quantity is None
            or quantity <= 0
        ):
            return False
        identity = (perm_id, client_id, order_id)
        if identity in open_orders_by_identity:
            return False
        open_orders_by_identity[identity] = order

    evidence_by_identity = {}
    for row in order_status_rows:
        if not isinstance(row, dict):
            return False

        order_id = row.get("order_id")
        perm_id = row.get("perm_id")
        client_id = row.get("client_id")
        status = row.get("status")
        filled = safe_float(row.get("filled"), None)
        remaining = safe_float(row.get("remaining"), None)
        average_fill_price = safe_float(
            row.get("average_fill_price"),
            None,
        )
        identity = (perm_id, client_id, order_id)
        if (
            type(order_id) is not int
            or type(perm_id) is not int
            or type(client_id) is not int
            or identity not in open_orders_by_identity
            or type(status) is not str
            or status not in ACTIVE_OPEN_ORDER_STATUSES
            or filled is None
            or filled < 0
            or remaining is None
            or remaining < 0
            or average_fill_price is None
            or average_fill_price < 0
            or (filled == 0 and average_fill_price != 0)
            or (filled > 0 and average_fill_price <= 0)
            or not math.isclose(
                filled + remaining,
                safe_float(
                    open_orders_by_identity[identity].get("quantity"),
                    None,
                ),
                rel_tol=1e-9,
                abs_tol=1e-9,
            )
        ):
            return False

        evidence_by_identity.setdefault(identity, set()).add((
            status,
            filled,
            remaining,
            average_fill_price,
        ))

    if set(evidence_by_identity) != set(open_orders_by_identity):
        return False

    return all(
        len(rows) == 1
        and next(iter(rows))[0]
        == open_orders_by_identity[identity].get("status")
        for identity, rows in evidence_by_identity.items()
    )


def open_order_execution_evidence_is_consistent(
    open_orders,
    order_status_rows,
    execution_rows,
):
    """Bind partial-fill callbacks to the exact active broker order."""
    if (
        not isinstance(open_orders, list)
        or not isinstance(order_status_rows, list)
        or not isinstance(execution_rows, list)
        or not open_order_status_evidence_is_consistent(
            open_orders,
            order_status_rows,
        )
    ):
        return False

    open_orders_by_identity = {
        (
            row.get("perm_id"),
            row.get("client_id"),
            row.get("order_id"),
        ): row
        for row in open_orders
    }
    status_by_identity = {}
    status_average_price_by_identity = {}
    for row in order_status_rows:
        identity = (
            row.get("perm_id"),
            row.get("client_id"),
            row.get("order_id"),
        )
        status_by_identity[identity] = safe_float(
            row.get("filled"),
            None,
        )
        status_average_price_by_identity[identity] = safe_float(
            row.get("average_fill_price"),
            None,
        )

    executions_by_identity = {}
    execution_ids = {}
    execution_correction_families = {}
    for row in execution_rows:
        if not isinstance(row, dict):
            return False

        identity = (
            row.get("perm_id"),
            row.get("client_id"),
            row.get("order_id"),
        )
        order = open_orders_by_identity.get(identity)
        execution_id = row.get("execution_id")
        correction_family = execution_correction_family(
            execution_id
        )
        shares = safe_float(row.get("shares"), None)
        cumulative_quantity = safe_float(
            row.get("cumulative_quantity"),
            None,
        )
        price = safe_float(row.get("price"), None)
        average_price = safe_float(row.get("average_price"), None)
        liquidation = row.get("liquidation")
        pending_price_revision = row.get("pending_price_revision")
        expected_side = (
            "BOT"
            if str(order.get("action") if order else "").upper() == "BUY"
            else "SLD"
        )
        normalized = (
            identity,
            row.get("account"),
            row.get("symbol"),
            row.get("security_type"),
            row.get("currency"),
            row.get("con_id"),
            row.get("side"),
            shares,
            cumulative_quantity,
            price,
            average_price,
            liquidation,
            pending_price_revision,
            row.get("time"),
        )
        if (
            order is None
            or type(row.get("request_id")) is not int
            or row["request_id"] != EXECUTIONS_REQUEST_ID
            or not isinstance(row.get("account"), str)
            or row["account"] != order.get("account")
            or not isinstance(execution_id, str)
            or not execution_id.strip()
            or correction_family is None
            or not isinstance(row.get("symbol"), str)
            or row["symbol"].strip().upper()
            != str(order.get("symbol") or "").strip().upper()
            or row.get("security_type") != "STK"
            or row.get("currency") != "USD"
            or row.get("con_id") != order.get("con_id")
            or row.get("side") != expected_side
            or shares is None
            or shares <= 0
            or cumulative_quantity is None
            or cumulative_quantity <= 0
            or cumulative_quantity
            > safe_float(order.get("quantity"), 0)
            or price is None
            or price <= 0
            or average_price is None
            or average_price <= 0
            or type(liquidation) is not int
            or liquidation != 0
            or type(pending_price_revision) is not bool
            or pending_price_revision is not False
            or (
                execution_id in execution_ids
                and execution_ids[execution_id] != normalized
            )
            or (
                correction_family in execution_correction_families
                and execution_correction_families[correction_family]
                != normalized
            )
        ):
            return False

        execution_ids[execution_id] = normalized
        execution_correction_families[correction_family] = normalized
        executions_by_identity.setdefault(identity, {})[
            correction_family
        ] = (
            shares,
            cumulative_quantity,
            average_price,
            price,
        )

    for identity, order in open_orders_by_identity.items():
        filled = status_by_identity.get(identity)
        average_fill_price = status_average_price_by_identity.get(identity)
        execution_families = executions_by_identity.get(identity, {})
        cumulative_quantities = [
            values[1]
            for values in execution_families.values()
        ]
        try:
            executed_shares = math.fsum(
                values[0]
                for values in execution_families.values()
            )
        except (OverflowError, ValueError):
            return False
        execution_notionals = [
            values[0] * values[3]
            for values in execution_families.values()
        ]
        if filled is None:
            return False
        if filled == 0:
            if cumulative_quantities:
                return False
            continue
        if any(not math.isfinite(value) for value in execution_notionals):
            return False
        try:
            weighted_average_price = (
                math.fsum(execution_notionals) / executed_shares
                if executed_shares > 0
                else None
            )
        except (OverflowError, ValueError):
            return False
        greatest_cumulative_quantity = max(cumulative_quantities, default=0)
        final_average_prices = [
            values[2]
            for values in execution_families.values()
            if math.isclose(
                values[1],
                greatest_cumulative_quantity,
                rel_tol=1e-9,
                abs_tol=1e-9,
            )
        ]
        if (
            not cumulative_quantities
            or average_fill_price is None
            or average_fill_price <= 0
            or weighted_average_price is None
            or not math.isfinite(weighted_average_price)
            or not math.isclose(
                greatest_cumulative_quantity,
                filled,
                rel_tol=1e-9,
                abs_tol=1e-9,
            )
            or not math.isclose(
                executed_shares,
                filled,
                rel_tol=1e-9,
                abs_tol=1e-9,
            )
            or not final_average_prices
            or not math.isclose(
                weighted_average_price,
                average_fill_price,
                rel_tol=1e-9,
                abs_tol=1e-9,
            )
            or any(
                not math.isclose(
                    average_price,
                    weighted_average_price,
                    rel_tol=1e-9,
                    abs_tol=1e-9,
                )
                for average_price in final_average_prices
            )
            or filled > safe_float(order.get("quantity"), 0)
        ):
            return False

    return True


def account_metric(
    snapshot,
    name
):
    if not isinstance(
        snapshot,
        dict
    ):
        return None

    summary = snapshot.get(
        "account_summary"
    )

    if not isinstance(
        summary,
        dict
    ):
        return None

    metric = summary.get(
        name
    )

    if not isinstance(
        metric,
        dict
    ):
        return None

    return safe_float(
        metric.get(
            "value"
        ),
        None
    )


def normalize_expected_positions(
    portfolio_rows
):
    if not isinstance(
        portfolio_rows,
        list
    ):
        raise ValueError(
            "portfolio_rows must be an explicit list."
        )

    expected = {}

    for row in portfolio_rows:
        if not isinstance(
            row,
            dict
        ):
            raise ValueError(
                "Every portfolio row must be an object."
            )

        ticker = row.get(
            "ticker"
        )

        if (
            not isinstance(
                ticker,
                str
            )
            or
            not ticker.strip()
        ):
            raise ValueError(
                "Every portfolio row requires a non-empty ticker."
            )

        ticker = ticker.strip().upper()

        if ticker in expected:
            raise ValueError(
                "Duplicate portfolio symbols are not allowed."
            )

        shares = safe_float(
            row.get(
                "shares"
            ),
            None
        )

        if shares is None:
            raise ValueError(
                "Portfolio share quantities must be finite numbers."
            )

        expected[
            ticker
        ] = shares

    return expected


def normalize_broker_positions(
    snapshot
):
    if not isinstance(
        snapshot,
        dict
    ):
        raise ValueError(
            "Broker snapshot must be an object."
        )

    positions = snapshot.get(
        "positions"
    )

    if not isinstance(
        positions,
        list
    ):
        raise ValueError(
            "Broker positions must be an explicit list."
        )

    broker = {}
    seen_symbols = set()
    seen_con_ids = set()
    seen_accounts = set()

    for row in positions:
        if not isinstance(
            row,
            dict
        ):
            raise ValueError(
                "Every broker position row must be an object."
            )

        ticker = row.get(
            "symbol"
        )

        if (
            not isinstance(
                ticker,
                str
            )
            or
            not ticker.strip()
        ):
            raise ValueError(
                "Every broker position requires a non-empty symbol."
            )

        ticker = ticker.strip().upper()

        account = row.get(
            "account"
        )
        security_type = row.get(
            "security_type"
        )
        currency = row.get(
            "currency"
        )
        con_id = row.get(
            "con_id"
        )
        position = safe_float(
            row.get(
                "position"
            ),
            None
        )

        if (
            not isinstance(
                account,
                str
            )
            or
            not account.strip()
        ):
            raise ValueError(
                "Every broker position requires an account fingerprint."
            )

        if security_type != "STK":
            raise ValueError(
                "Only stock broker positions are supported."
            )

        if currency != "USD":
            raise ValueError(
                "Only USD broker positions are supported."
            )

        if (
            type(con_id)
            is not int
            or
            con_id
            <=
            0
        ):
            raise ValueError(
                "Every broker position requires a positive integer conId."
            )

        if position is None:
            raise ValueError(
                "Broker position quantities must be finite numbers."
            )

        if ticker in seen_symbols:
            raise ValueError(
                "Duplicate broker symbols are ambiguous."
            )

        if con_id in seen_con_ids:
            raise ValueError(
                "Duplicate broker conIds are ambiguous."
            )

        seen_symbols.add(
            ticker
        )
        seen_con_ids.add(
            con_id
        )
        seen_accounts.add(
            account.strip()
        )

        if len(
            seen_accounts
        ) > 1:
            raise ValueError(
                "Cross-account broker positions are not supported."
            )

        if abs(
            position
        ) < 1e-9:
            continue

        broker[
            ticker
        ] = position

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
    if not isinstance(
        broker_snapshot,
        dict
    ):
        broker_snapshot = {}

    status = broker_snapshot.get(
        "status"
    )

    config = broker_snapshot.get(
        "config"
    )

    if not isinstance(
        config,
        dict
    ):
        config = {}

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

    paper_account_guard = broker_snapshot.get(
        "paper_account_guard"
    )

    if not isinstance(
        paper_account_guard,
        dict
    ):
        paper_account_guard = {}

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

    verified_account_rows = paper_account_guard.get(
        "verified_account_fingerprints"
    )

    verified_account_fingerprints_valid = (
        isinstance(
            verified_account_rows,
            list
        )
        and bool(
            verified_account_rows
        )
        and all(
            isinstance(
                item,
                str
            )
            and bool(
                item.strip()
            )
            for item in verified_account_rows
        )
        and len({
            item.strip()
            for item in verified_account_rows
        })
        ==
        len(
            verified_account_rows
        )
    )

    verified_account_fingerprints = (
        sorted({
            item.strip()
            for item in verified_account_rows
        })
        if verified_account_fingerprints_valid
        else []
    )

    add_check(
        "verified_account_fingerprint_payload_valid",
        verified_account_fingerprints_valid,
        True,
        (
            "Verified Paper account fingerprints must be a non-empty "
            "list of non-empty strings."
        )
    )

    account_summary_fingerprint_rows = broker_snapshot.get(
        "account_summary_account_fingerprints"
    )

    account_summary_fingerprints_valid = (
        isinstance(
            account_summary_fingerprint_rows,
            list
        )
        and bool(
            account_summary_fingerprint_rows
        )
        and all(
            isinstance(
                item,
                str
            )
            and bool(
                item.strip()
            )
            for item in account_summary_fingerprint_rows
        )
        and len({
            item.strip()
            for item in account_summary_fingerprint_rows
        })
        ==
        len(
            account_summary_fingerprint_rows
        )
    )

    account_summary_account_fingerprints = (
        sorted({
            item.strip()
            for item in account_summary_fingerprint_rows
        })
        if account_summary_fingerprints_valid
        else []
    )

    add_check(
        "account_summary_accounts_match_managed_accounts",
        (
            verified_account_fingerprints_valid
            and account_summary_fingerprints_valid
            and account_summary_account_fingerprints
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
        "gateway_read_only_configuration_independently_attested",
        broker_snapshot.get(
            "gateway_read_only_configuration_independently_attested"
        )
        is True,
        True,
        (
            "IB Gateway/TWS API Read-Only configuration must be independently "
            "attested; connector-side flags cannot self-attest this control."
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
        "broker_mutation_surface_hard_blocked",
        broker_snapshot.get(
            "broker_mutation_surface_hard_blocked"
        )
        is True,
        True,
        (
            "The read-only connector must hard-block order placement, "
            "cancellation, global cancellation, option exercise, FA "
            "replacement and automatic TWS-order binding."
        )
    )

    add_check(
        "nonbinding_open_order_observation",
        broker_snapshot.get(
            "open_order_observation_mode"
        )
        ==
        "REQ_ALL_OPEN_ORDERS_NON_BINDING",
        True,
        (
            "Open-order observation must use reqAllOpenOrders so the "
            "probe does not bind TWS orders to the API client."
        )
    )

    add_check(
        "nonzero_api_client_id",
        (
            config.get(
                "client_id_valid"
            )
            is True
            and
            type(
                config.get(
                    "client_id"
                )
            )
            is int
            and
            config.get(
                "client_id"
            )
            >
            0
        ),
        True,
        (
            "Read-only diagnostics must never use special IBKR clientId 0."
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
    guard_account_count = safe_float(
        paper_account_guard.get(
            "account_count"
        ),
        -1
    )
    snapshot_accounts = broker_snapshot.get("accounts")
    snapshot_accounts_valid = (
        isinstance(
            snapshot_accounts,
            list
        )
        and bool(
            snapshot_accounts
        )
        and all(
            isinstance(
                item,
                str
            )
            and bool(
                item.strip()
            )
            for item in snapshot_accounts
        )
        and len({
            item.strip()
            for item in snapshot_accounts
        })
        ==
        len(
            snapshot_accounts
        )
    )

    snapshot_account_fingerprints = (
        sorted({
            item.strip()
            for item in snapshot_accounts
        })
        if snapshot_accounts_valid
        else []
    )

    add_check(
        "managed_account_identity_consistent",
        (
            verified_account_fingerprints_valid
            and snapshot_accounts_valid
            and snapshot_account_fingerprints
            == verified_account_fingerprints
            and account_count
            == guard_account_count
            == len(verified_account_fingerprints)
            == len(snapshot_accounts)
        ),
        True,
        (
            "Snapshot account list/count and account-guard fingerprints "
            "must describe the exact same Paper account set."
        )
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

    requests_complete = broker_snapshot.get(
        "requests_complete"
    )

    if not isinstance(
        requests_complete,
        dict
    ):
        requests_complete = {}

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

    add_check(
        "execution_snapshot_complete",
        requests_complete.get(
            "executions"
        )
        is True,
        True,
        (
            "Execution request must reach execDetailsEnd before read-only "
            "readiness can reconcile partial fills."
        )
    )

    open_orders = broker_snapshot.get(
        "open_orders"
    )
    open_orders_payload_valid = open_order_payload_is_valid(
        open_orders
    )
    add_check(
        "open_orders_payload_valid",
        open_orders_payload_valid,
        True,
        (
            "Open-order payload must contain valid identifiers, symbols, "
            "USD stock contract identity, BUY/SELL direction, positive "
            "finite quantity and an unambiguous symbol-to-conId mapping."
        ),
    )

    open_order_identifiers_unique = (
        open_orders_payload_valid
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
    add_check(
        "open_order_identifiers_unique",
        open_order_identifiers_unique,
        True,
        (
            "Every reported open order must have a unique account-wide "
            "permId and unique clientId/orderId pair."
        ),
    )

    open_order_statuses_active = (
        open_orders_payload_valid
        and all(
            type(row.get("status")) is str
            and row["status"] in ACTIVE_OPEN_ORDER_STATUSES
            for row in open_orders
        )
        and open_order_status_evidence_is_consistent(
            open_orders,
            broker_snapshot.get("order_status"),
        )
    )
    add_check(
        "open_order_statuses_active",
        open_order_statuses_active,
        True,
        (
            "Every reported open order must carry matching, complete and "
            "unambiguous active status evidence from both IBKR callbacks."
        ),
    )

    open_order_execution_evidence_consistent = (
        open_order_statuses_active
        and open_order_execution_evidence_is_consistent(
            open_orders,
            broker_snapshot.get("order_status"),
            broker_snapshot.get("executions"),
        )
    )
    add_check(
        "open_order_execution_evidence_consistent",
        open_order_execution_evidence_consistent,
        True,
        (
            "Every partial fill must carry complete execDetails evidence "
            "bound to the fixed execution request ID, the verified Paper "
            "account, the same permId/clientId/orderId and cumulative "
            "filled quantity reported by orderStatus; correction-family "
            "callbacks must be identical except for execution ID revision, "
            "and unique-family shares must sum to the filled quantity."
        ),
    )

    open_order_accounts_verified = (
        open_orders_payload_valid
        and open_order_identifiers_unique
        and all(
            isinstance(
                row.get(
                    "account"
                ),
                str
            )
            and row[
                "account"
            ]
            in verified_account_fingerprints
            for row in open_orders
        )
    )
    add_check(
        "open_order_accounts_match_verified_paper_accounts",
        open_order_accounts_verified,
        True,
        "Every reported open order must originate from a verified Paper account.",
    )

    positions = broker_snapshot.get(
        "positions"
    )
    positions_payload_valid = (
        isinstance(
            positions,
            list
        )
        and all(
            isinstance(
                row,
                dict
            )
            and isinstance(
                row.get(
                    "symbol"
                ),
                str
            )
            and bool(
                row.get(
                    "symbol"
                ).strip()
            )
            and safe_float(
                row.get(
                    "position"
                ),
                None
            )
            is not None
            for row in positions
        )
    )
    add_check(
        "positions_payload_valid",
        positions_payload_valid,
        True,
        (
            "Position payload must be an explicit list with valid symbols "
            "and finite numeric quantities."
        ),
    )

    position_accounts_verified = (
        positions_payload_valid
        and all(
            isinstance(
                row.get(
                    "account"
                ),
                str
            )
            and row[
                "account"
            ]
            in verified_account_fingerprints
            for row in positions
        )
    )
    add_check(
        "position_accounts_match_verified_paper_accounts",
        position_accounts_verified,
        True,
        "Every reported position must originate from a verified Paper account.",
    )

    # Fail closed on malformed portfolio quantities and ambiguous identities.
    portfolio_rows_valid = (
        isinstance(portfolio_rows, list)
        and all(
            isinstance(row, dict)
            and isinstance(row.get("ticker"), str)
            and bool(row["ticker"].strip())
            and safe_float(row.get("shares"), None) is not None
            for row in portfolio_rows
        )
    )
    portfolio_symbols = (
        [row["ticker"].strip().upper() for row in portfolio_rows]
        if portfolio_rows_valid else []
    )
    add_check(
        "portfolio_quantities_and_symbols_valid",
        portfolio_rows_valid and len(portfolio_symbols) == len(set(portfolio_symbols)),
        True,
        "Portfolio symbols must be unique and quantities finite and explicit.",
    )

    position_instruments_valid = (
        positions_payload_valid
        and all(
            isinstance(row.get("security_type"), str)
            and row["security_type"] == "STK"
            and isinstance(row.get("currency"), str)
            and row["currency"] == "USD"
            and isinstance(row.get("account"), str)
            and row["account"] in verified_account_fingerprints
            and type(row.get("con_id")) is int
            and row["con_id"] > 0
            for row in positions
        )
    )
    position_symbols = (
        [row["symbol"].strip().upper() for row in positions]
        if position_instruments_valid else []
    )
    position_con_ids = (
        [row["con_id"] for row in positions]
        if position_instruments_valid else []
    )
    position_identity_keys = (
        [(row["account"], row["symbol"].strip().upper(),
          row["security_type"], row["currency"], row["con_id"])
         for row in positions]
        if position_instruments_valid else []
    )
    add_check(
        "position_instruments_unambiguous",
        position_instruments_valid
        and len(position_identity_keys) == len(set(position_identity_keys))
        and len(position_symbols) == len(set(position_symbols))
        and len(position_con_ids) == len(set(position_con_ids)),
        True,
        (
            "Only uniquely identified USD stock positions with positive "
            "IBKR conIds from verified accounts are supported."
        ),
    )

    position_sync = (
        compare_positions(portfolio_rows, broker_snapshot)
        if portfolio_rows_valid and positions_payload_valid
        and position_instruments_valid
        and len(portfolio_symbols) == len(set(portfolio_symbols))
        and len(position_identity_keys) == len(set(position_identity_keys))
        and len(position_symbols) == len(set(position_symbols))
        and len(position_con_ids) == len(set(position_con_ids))
        and requests_complete.get("positions") is True
        and position_accounts_verified
        else {
            "expected_position_count": 0,
            "broker_position_count": 0,
            "mismatch_count": None,
            "all_positions_match": False,
            "rows": [],
            "status": "BLOCKED_INVALID_POSITION_INPUT",
        }
    )

    add_check(
        "portfolio_sync_observed",
        position_sync.get("status") != "BLOCKED_INVALID_POSITION_INPUT"
        and isinstance(position_sync.get("broker_position_count"), int)
        and position_sync["broker_position_count"] >= 0,
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

    attestation_check_name = (
        "gateway_read_only_configuration_independently_attested"
    )
    non_attestation_required_failures = [
        item
        for item in required_failures
        if item.get(
            "check"
        )
        !=
        attestation_check_name
    ]
    diagnostic_read_only_ready = (
        status
        !=
        "DISABLED"
        and
        not non_attestation_required_failures
    )

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

        "gateway_read_only_configuration_independently_attested":
        broker_snapshot.get(
            "gateway_read_only_configuration_independently_attested"
        )
        is True,

        "diagnostic_read_only_ready":
        diagnostic_read_only_ready,

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
            (
                "INDEPENDENT_GATEWAY_READ_ONLY_ATTESTATION"
                if diagnostic_read_only_ready
                else
                "ESTABLISH_PAPER_READ_ONLY_CONNECTION"
            )
        )
    }
