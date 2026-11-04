"""
V8.9.5 AURORA IBKR Gateway Connector — Paper Read-Only Proof Foundation

Purpose:
- Connect to Interactive Brokers TWS / IB Gateway through the official TWS API
- Read paper account summary, positions, open orders and execution feedback
- Keep LIVE trading disabled at the connector layer
- Fail closed when the official IBKR Python API is unavailable
- Never store credentials in the repository

Default configuration:
- Disabled unless AURORA_IBKR_ENABLED=true
- Mode: PAPER
- Host: 127.0.0.1
- Paper IB Gateway port: 4002
- Client ID: 82
- Read-only snapshot only

IBKR's official Python API must be installed from the official TWS API package
on the machine running IB Gateway. This repository intentionally does not
install an unofficial PyPI ibapi package.
"""

from datetime import datetime, timezone
import math
import os
import threading
import time

from engines.ibkr_account_guard import (
    account_fingerprint,
    evaluate_paper_account_identity,
)
from engines.ibkr_paper_readiness_engine import EXECUTIONS_REQUEST_ID


try:
    from ibapi.client import EClient
    from ibapi.execution import ExecutionFilter
    from ibapi.wrapper import EWrapper

    IBAPI_AVAILABLE = True
    IBAPI_IMPORT_ERROR = None

except Exception as error:
    EClient = object
    EWrapper = object

    IBAPI_AVAILABLE = False
    IBAPI_IMPORT_ERROR = str(
        error
    )


ENGINE_VERSION = (
    "V8.9.5 IBKR Gateway Connector"
)

LIVE_TRADING_ALLOWED = False

BROKER_MUTATION_METHODS_HARD_BLOCKED = (
    "placeOrder",
    "cancelOrder",
    "reqGlobalCancel",
    "exerciseOptions",
    "replaceFA",
    "reqAutoOpenOrders",
)

OPEN_ORDER_OBSERVATION_MODE = (
    "REQ_ALL_OPEN_ORDERS_NON_BINDING"
)

def env_bool(
    name,
    default=False
):
    value = os.getenv(
        name
    )

    if value is None:
        return default

    return str(
        value
    ).strip().lower() in {
        "1",
        "true",
        "yes",
        "on"
    }


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


def mask_account(
    account
):
    return account_fingerprint(account)


def load_ibkr_config():
    requested_mode = (
        os.getenv(
            "AURORA_IBKR_MODE",
            "PAPER"
        )
        .strip()
        .upper()
    )

    mode_valid = requested_mode in {
        "PAPER",
        "LIVE"
    }

    mode = (
        requested_mode
        if mode_valid
        else
        "INVALID"
    )

    default_port = (
        4002
        if mode == "PAPER"
        else 4001
    )

    try:
        port = int(
            os.getenv(
                "AURORA_IBKR_PORT",
                str(
                    default_port
                )
            )
        )
        port_valid = (
            1
            <=
            port
            <=
            65535
        )

    except (
        TypeError,
        ValueError,
        OverflowError
    ):
        port = -1
        port_valid = False

    try:
        client_id = int(
            os.getenv(
                "AURORA_IBKR_CLIENT_ID",
                "82"
            )
        )
        client_id_valid = (
            1
            <=
            client_id
            <=
            2147483647
        )

    except (
        TypeError,
        ValueError,
        OverflowError
    ):
        client_id = -1
        client_id_valid = False

    try:
        timeout_seconds = float(
            os.getenv(
                "AURORA_IBKR_TIMEOUT_SECONDS",
                "8"
            )
        )
        timeout_valid = (
            math.isfinite(
                timeout_seconds
            )
            and
            2.0
            <=
            timeout_seconds
            <=
            30.0
        )

    except (
        TypeError,
        ValueError,
        OverflowError
    ):
        timeout_seconds = -1.0
        timeout_valid = False

    return {
        "enabled":
        env_bool(
            "AURORA_IBKR_ENABLED",
            False
        ),

        "mode":
        mode,

        "mode_valid":
        mode_valid,

        "host":
        os.getenv(
            "AURORA_IBKR_HOST",
            "127.0.0.1"
        ).strip(),

        "port":
        port,

        "port_valid":
        port_valid,

        "client_id":
        client_id,

        "client_id_valid":
        client_id_valid,

        "timeout_seconds":
        timeout_seconds,

        "timeout_valid":
        timeout_valid,

        "read_only":
        True,

        "live_trading_allowed":
        LIVE_TRADING_ALLOWED
    }


if IBAPI_AVAILABLE:

    class _IBKRSnapshotApp(
        EWrapper,
        EClient
    ):

        def __init__(self):
            EWrapper.__init__(
                self
            )

            EClient.__init__(
                self,
                self
            )

            self.next_order_id = None

            self.accounts = []

            self.account_summary_rows = []

            self.positions = []

            self.open_orders = []

            self.order_status_rows = []

            self.execution_rows = []

            self.errors = []

            self.connected_event = (
                threading.Event()
            )

            self.managed_accounts_event = (
                threading.Event()
            )

            self.account_summary_event = (
                threading.Event()
            )

            self.positions_event = (
                threading.Event()
            )

            self.open_orders_event = (
                threading.Event()
            )

            self.executions_event = (
                threading.Event()
            )


        def nextValidId(
            self,
            orderId
        ):
            self.next_order_id = (
                orderId
            )

            self.connected_event.set()


        def managedAccounts(
            self,
            accountsList
        ):
            self.accounts = [
                item.strip()
                for item in (
                    accountsList
                    or
                    ""
                ).split(
                    ","
                )
                if item.strip()
            ]

            self.managed_accounts_event.set()


        def _hard_block_broker_mutation(
            self,
            operation
        ):
            raise RuntimeError(
                f"{operation} is hard-blocked by the AURORA "
                "IBKR read-only connector."
            )


        def placeOrder(
            self,
            *args,
            **kwargs
        ):
            return self._hard_block_broker_mutation(
                "placeOrder"
            )


        def cancelOrder(
            self,
            *args,
            **kwargs
        ):
            return self._hard_block_broker_mutation(
                "cancelOrder"
            )


        def reqGlobalCancel(
            self,
            *args,
            **kwargs
        ):
            return self._hard_block_broker_mutation(
                "reqGlobalCancel"
            )


        def exerciseOptions(
            self,
            *args,
            **kwargs
        ):
            return self._hard_block_broker_mutation(
                "exerciseOptions"
            )


        def replaceFA(
            self,
            *args,
            **kwargs
        ):
            return self._hard_block_broker_mutation(
                "replaceFA"
            )


        def reqAutoOpenOrders(
            self,
            *args,
            **kwargs
        ):
            return self._hard_block_broker_mutation(
                "reqAutoOpenOrders"
            )


        def accountSummary(
            self,
            reqId,
            account,
            tag,
            value,
            currency
        ):
            self.account_summary_rows.append({
                "account":
                account,

                "tag":
                tag,

                "value":
                value,

                "currency":
                currency
            })


        def accountSummaryEnd(
            self,
            reqId
        ):
            self.account_summary_event.set()


        def position(
            self,
            account,
            contract,
            position,
            avgCost
        ):
            symbol = getattr(
                contract,
                "symbol",
                None
            )

            sec_type = getattr(
                contract,
                "secType",
                None
            )

            currency = getattr(
                contract,
                "currency",
                None
            )

            exchange = getattr(
                contract,
                "exchange",
                None
            )

            con_id = getattr(
                contract,
                "conId",
                None
            )

            if (
                type(con_id)
                is not int
                or
                con_id
                <=
                0
            ):
                con_id = None

            self.positions.append({
                "account":
                account,

                "symbol":
                symbol,

                "security_type":
                sec_type,

                "currency":
                currency,

                "exchange":
                exchange,

                "con_id":
                con_id,

                "position":
                safe_float(
                    position,
                    None
                ),

                "average_cost":
                safe_float(
                    avgCost,
                    None
                )
            })


        def positionEnd(
            self
        ):
            self.positions_event.set()


        def openOrder(
            self,
            orderId,
            contract,
            order,
            orderState
        ):
            self.open_orders.append({
                "order_id":
                orderId,

                "perm_id":
                (
                    getattr(order, "permId", None)
                    if type(getattr(order, "permId", None)) is int
                    and getattr(order, "permId", None) > 0
                    else None
                ),

                "client_id":
                (
                    getattr(order, "clientId", None)
                    if type(getattr(order, "clientId", None)) is int
                    and getattr(order, "clientId", None) >= 0
                    else None
                ),

                "account":
                mask_account(
                    getattr(
                        order,
                        "account",
                        None
                    )
                ),

                "symbol":
                getattr(
                    contract,
                    "symbol",
                    None
                ),

                "security_type":
                getattr(
                    contract,
                    "secType",
                    None
                ),

                "currency":
                getattr(
                    contract,
                    "currency",
                    None
                ),

                "con_id":
                (
                    getattr(contract, "conId", None)
                    if type(getattr(contract, "conId", None)) is int
                    and getattr(contract, "conId", None) > 0
                    else None
                ),

                "action":
                getattr(
                    order,
                    "action",
                    None
                ),

                "order_type":
                getattr(
                    order,
                    "orderType",
                    None
                ),

                "quantity":
                safe_float(
                    getattr(
                        order,
                        "totalQuantity",
                        None
                    ),
                    None
                ),

                "limit_price":
                safe_float(
                    getattr(
                        order,
                        "lmtPrice",
                        None
                    ),
                    None
                ),

                "status":
                getattr(
                    orderState,
                    "status",
                    None
                )
            })


        def openOrderEnd(
            self
        ):
            self.open_orders_event.set()


        def orderStatus(
            self,
            orderId,
            status,
            filled,
            remaining,
            avgFillPrice,
            permId,
            parentId,
            lastFillPrice,
            clientId,
            whyHeld,
            mktCapPrice
        ):
            self.order_status_rows.append({
                "order_id":
                orderId,

                "perm_id":
                (
                    permId
                    if type(permId) is int and permId > 0
                    else None
                ),

                "client_id":
                (
                    clientId
                    if type(clientId) is int and clientId >= 0
                    else None
                ),

                "status":
                status,

                "filled":
                safe_float(
                    filled,
                    None
                ),

                "remaining":
                safe_float(
                    remaining,
                    None
                ),

                "average_fill_price":
                safe_float(
                    avgFillPrice,
                    None
                )
            })


        def execDetails(
            self,
            reqId,
            contract,
            execution
        ):
            if reqId != EXECUTIONS_REQUEST_ID:
                return

            self.execution_rows.append({
                "request_id":
                reqId,

                "order_id":
                (
                    getattr(execution, "orderId", None)
                    if type(getattr(execution, "orderId", None)) is int
                    and getattr(execution, "orderId", None) >= 0
                    else None
                ),

                "perm_id":
                (
                    getattr(execution, "permId", None)
                    if type(getattr(execution, "permId", None)) is int
                    and getattr(execution, "permId", None) > 0
                    else None
                ),

                "client_id":
                (
                    getattr(execution, "clientId", None)
                    if type(getattr(execution, "clientId", None)) is int
                    and getattr(execution, "clientId", None) >= 0
                    else None
                ),

                "symbol":
                getattr(
                    contract,
                    "symbol",
                    None
                ),

                "security_type":
                getattr(
                    contract,
                    "secType",
                    None
                ),

                "currency":
                getattr(
                    contract,
                    "currency",
                    None
                ),

                "con_id":
                (
                    getattr(contract, "conId", None)
                    if type(getattr(contract, "conId", None)) is int
                    and getattr(contract, "conId", None) > 0
                    else None
                ),

                "execution_id":
                getattr(
                    execution,
                    "execId",
                    None
                ),

                "side":
                getattr(
                    execution,
                    "side",
                    None
                ),

                "shares":
                safe_float(
                    getattr(
                        execution,
                        "shares",
                        None
                    ),
                    None
                ),

                "cumulative_quantity":
                safe_float(
                    getattr(
                        execution,
                        "cumQty",
                        None
                    ),
                    None
                ),

                "price":
                safe_float(
                    getattr(
                        execution,
                        "price",
                        None
                    ),
                    None
                ),

                "time":
                getattr(
                    execution,
                    "time",
                    None
                )
            })


        def execDetailsEnd(
            self,
            reqId
        ):
            if reqId == EXECUTIONS_REQUEST_ID:
                self.executions_event.set()


        def error(
            self,
            reqId,
            errorCode,
            errorString,
            advancedOrderRejectJson=""
        ):
            self.errors.append({
                "request_id":
                reqId,

                "code":
                errorCode,

                "message":
                errorString
            })


        def connectionClosed(
            self
        ):
            self.connected_event.clear()


def _account_summary_dict(
    rows
):
    summary = {}

    for row in rows:
        tag = row.get(
            "tag"
        )

        if not tag:
            continue

        summary[
            tag
        ] = {
            "value":
            safe_float(
                row.get(
                    "value"
                ),
                row.get(
                    "value"
                )
            ),

            "currency":
            row.get(
                "currency"
            )
        }

    return summary


def _account_summary_fingerprints(
    rows
):
    return sorted({
        mask_account(
            row.get(
                "account"
            )
        )
        for row in (
            rows
            or
            []
        )
        if row.get(
            "account"
        )
    })


def _sanitize_positions(
    positions
):
    sanitized = []

    for item in positions:
        sanitized.append({
            "account":
            mask_account(
                item.get(
                    "account"
                )
            ),

            "symbol":
            item.get(
                "symbol"
            ),

            "security_type":
            item.get(
                "security_type"
            ),

            "currency":
            item.get(
                "currency"
            ),

            "exchange":
            item.get(
                "exchange"
            ),

            "con_id":
            item.get(
                "con_id"
            ),

            "position":
            item.get(
                "position"
            ),

            "average_cost":
            item.get(
                "average_cost"
            )
        })

    return sanitized


def _sanitize_errors(
    errors,
    accounts
):
    sanitized = []

    for item in (
        errors
        or
        []
    ):
        message = str(
            item.get(
                "message",
                ""
            )
        )

        for account in (
            accounts
            or
            []
        ):
            if account:
                message = message.replace(
                    str(account),
                    mask_account(
                        account
                    )
                )

        sanitized.append({
            "request_id":
            item.get(
                "request_id"
            ),

            "code":
            item.get(
                "code"
            ),

            "message":
            message
        })

    return sanitized


def get_ibkr_read_only_snapshot():
    config = load_ibkr_config()

    endpoint_safe = (
        config.get("mode") == "PAPER"
        and config.get("host") == "127.0.0.1"
        and config.get("port") == 4002
    )

    base = {
        "engine":
        ENGINE_VERSION,

        "timestamp":
        datetime.now(
            timezone.utc
        ).isoformat(),

        "config": {
            "enabled":
            config.get(
                "enabled"
            ),

            "mode":
            config.get(
                "mode"
            ),

            "mode_valid":
            config.get(
                "mode_valid"
            ),

            "host":
            config.get(
                "host"
            ),

            "port":
            config.get(
                "port"
            ),

            "port_valid":
            config.get(
                "port_valid"
            ),

            "client_id":
            config.get(
                "client_id"
            ),

            "client_id_valid":
            config.get(
                "client_id_valid"
            ),

            "timeout_seconds":
            config.get(
                "timeout_seconds"
            ),

            "timeout_valid":
            config.get(
                "timeout_valid"
            ),

            "read_only":
            True,

            "live_trading_allowed":
            False,

            "endpoint_safe":
            endpoint_safe
        },

        "official_ibapi_available":
        IBAPI_AVAILABLE,

        "order_submission_hard_blocked":
        True,

        "broker_mutation_surface_hard_blocked":
        True,

        "blocked_broker_mutation_methods":
        list(
            BROKER_MUTATION_METHODS_HARD_BLOCKED
        ),

        "open_order_observation_mode":
        OPEN_ORDER_OBSERVATION_MODE,

        "client_zero_binding_hard_blocked":
        (
            config.get(
                "client_id_valid"
            )
            is True
            and
            config.get(
                "client_id"
            )
            !=
            0
        ),

        "gateway_read_only_configuration_independently_attested":
        False,

        "live_trading_allowed":
        False
    }

    if not config.get(
        "enabled"
    ):
        return {
            **base,

            "status":
            "DISABLED",

            "connection_status":
            "NOT_ATTEMPTED",

            "reason":
            (
                "Set AURORA_IBKR_ENABLED=true on the IB Gateway VPS "
                "to run the paper read-only probe."
            )
        }

    if (
        config.get(
            "mode"
        )
        !=
        "PAPER"
    ):
        return {
            **base,

            "status":
            "BLOCKED",

            "connection_status":
            "NOT_ATTEMPTED",

            "reason":
            (
                "V8.9.5 connector permits an explicit PAPER mode only. "
                "LIVE and invalid modes are hard-blocked."
            )
        }

    if config.get(
        "port_valid"
    ) is not True:
        return {
            **base,

            "status":
            "BLOCKED",

            "connection_status":
            "NOT_ATTEMPTED",

            "reason":
            "INVALID_IBKR_PORT"
        }

    if not endpoint_safe:
        return {
            **base,

            "status":
            "BLOCKED",

            "connection_status":
            "NOT_ATTEMPTED",

            "reason":
            (
                "CONFIG_SAFETY_BLOCK: IBKR paper read-only access is "
                "restricted to 127.0.0.1:4002."
            )
        }

    if config.get(
        "client_id_valid"
    ) is not True:
        return {
            **base,

            "status":
            "BLOCKED",

            "connection_status":
            "NOT_ATTEMPTED",

            "reason":
            "INVALID_IBKR_CLIENT_ID"
        }

    if config.get(
        "timeout_valid"
    ) is not True:
        return {
            **base,

            "status":
            "BLOCKED",

            "connection_status":
            "NOT_ATTEMPTED",

            "reason":
            "INVALID_IBKR_TIMEOUT_SECONDS"
        }

    if not IBAPI_AVAILABLE:
        return {
            **base,

            "status":
            "NOT_INSTALLED",

            "connection_status":
            "NOT_ATTEMPTED",

            "reason":
            (
                "Official IBKR TWS Python API is not installed on this machine."
            ),

            "import_error":
            IBAPI_IMPORT_ERROR
        }

    app = _IBKRSnapshotApp()

    timeout = config.get(
        "timeout_seconds",
        8.0
    )

    network_thread = None

    try:
        app.connect(
            config.get(
                "host"
            ),
            config.get(
                "port"
            ),
            clientId=config.get(
                "client_id"
            )
        )

        network_thread = (
            threading.Thread(
                target=app.run,
                daemon=True
            )
        )

        network_thread.start()

        connected = (
            app.connected_event.wait(
                timeout=timeout
            )
        )

        if not connected:
            return {
                **base,

                "status":
                "NOT_CONNECTED",

                "connection_status":
                "TIMEOUT",

                "reason":
                (
                    "IB Gateway/TWS did not return nextValidId before timeout."
                ),

                "errors":
                _sanitize_errors(
                    app.errors[-20:],
                    app.accounts
                )
            }

        app.reqManagedAccts()

        app.reqAccountSummary(
            8301,
            "All",
            (
                "NetLiquidation,"
                "TotalCashValue,"
                "AvailableFunds,"
                "BuyingPower,"
                "GrossPositionValue,"
                "MaintMarginReq,"
                "ExcessLiquidity"
            )
        )

        app.reqPositions()

        app.reqAllOpenOrders()

        app.reqExecutions(
            EXECUTIONS_REQUEST_ID,
            ExecutionFilter()
        )

        deadline = (
            time.time()
            +
            timeout
        )

        while time.time() < deadline:
            if (
                app.managed_accounts_event.is_set()
                and
                app.account_summary_event.is_set()
                and
                app.positions_event.is_set()
                and
                app.open_orders_event.is_set()
                and
                app.executions_event.is_set()
            ):
                break

            time.sleep(
                0.05
            )

        try:
            app.cancelAccountSummary(
                8301
            )
        except Exception:
            pass

        try:
            app.cancelPositions()
        except Exception:
            pass

        summary = _account_summary_dict(
            app.account_summary_rows
        )

        account_summary_account_fingerprints = (
            _account_summary_fingerprints(
                app.account_summary_rows
            )
        )

        masked_accounts = [
            mask_account(
                account
            )
            for account in app.accounts
        ]

        requests_complete = (
            app.managed_accounts_event.is_set()
            and
            app.account_summary_event.is_set()
            and
            app.positions_event.is_set()
            and
            app.open_orders_event.is_set()
            and
            app.executions_event.is_set()
        )

        account_guard = evaluate_paper_account_identity(
            app.accounts
        )

        if not account_guard.get("paper_account_verified"):
            status = "BLOCKED"
        elif requests_complete:
            status = "CONNECTED"
        else:
            status = "PARTIAL"

        return {
            **base,

            "status":
            status,

            "connection_status":
            "CONNECTED",

            "accounts":
            masked_accounts,

            "account_count":
            len(
                masked_accounts
            ),

            "paper_account_guard":
            account_guard,

            "next_order_id_received":
            app.next_order_id
            is not None,

            "account_summary":
            summary,

            "account_summary_account_fingerprints":
            account_summary_account_fingerprints,

            "positions":
            _sanitize_positions(
                app.positions
            ),

            "position_count":
            len(
                app.positions
            ),

            "open_orders":
            app.open_orders,

            "open_order_count":
            len(
                app.open_orders
            ),

            "order_status":
            app.order_status_rows,

            "executions":
            app.execution_rows,

            "errors":
            _sanitize_errors(
                app.errors[-20:],
                app.accounts
            ),

            "requests_complete": {
                "managed_accounts":
                app.managed_accounts_event.is_set(),

                "account_summary":
                app.account_summary_event.is_set(),

                "positions":
                app.positions_event.is_set(),

                "open_orders":
                app.open_orders_event.is_set(),

                "executions":
                app.executions_event.is_set()
            }
        }

    except Exception as error:
        return {
            **base,

            "status":
            "ERROR",

            "connection_status":
            "FAILED",

            "reason":
            str(
                error
            ),

            "errors":
            _sanitize_errors(
                getattr(
                    app,
                    "errors",
                    []
                )[-20:],
                getattr(
                    app,
                    "accounts",
                    []
                )
            )
        }

    finally:
        try:
            if app.isConnected():
                app.disconnect()
        except Exception:
            pass
