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
import os
import threading
import time

from engines.ibkr_account_guard import (
    account_fingerprint,
    evaluate_paper_account_identity,
)


try:
    from ibapi.client import EClient
    from ibapi.wrapper import EWrapper
    from ibapi.execution import ExecutionFilter

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
    try:
        return float(
            value
        )
    except (
        TypeError,
        ValueError
    ):
        return default


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

    except Exception:
        port = default_port

    try:
        client_id = int(
            os.getenv(
                "AURORA_IBKR_CLIENT_ID",
                "82"
            )
        )

    except Exception:
        client_id = 82

    try:
        timeout_seconds = float(
            os.getenv(
                "AURORA_IBKR_TIMEOUT_SECONDS",
                "8"
            )
        )

    except Exception:
        timeout_seconds = 8.0

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

        "client_id":
        client_id,

        "timeout_seconds":
        max(
            2.0,
            min(
                timeout_seconds,
                30.0
            )
        ),

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

            self.executions_event = threading.Event()


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


        def placeOrder(
            self,
            orderId,
            contract,
            order
        ):
            raise RuntimeError(
                "Order submission is hard-blocked by the AURORA "
                "IBKR read-only connector."
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

                "position":
                safe_float(
                    position,
                    0.0
                ),

                "average_cost":
                safe_float(
                    avgCost,
                    0.0
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

                "status":
                status,

                "filled":
                safe_float(
                    filled,
                    0.0
                ),

                "remaining":
                safe_float(
                    remaining,
                    0.0
                ),

                "average_fill_price":
                safe_float(
                    avgFillPrice,
                    0.0
                )
            })


        def execDetailsEnd(self, reqId):
            if reqId == 8302:
                self.executions_event.set()

        def execDetails(
            self,
            reqId,
            contract,
            execution
        ):
            self.execution_rows.append({
                "symbol":
                getattr(
                    contract,
                    "symbol",
                    None
                ),

                "order_id": getattr(execution, "orderId", None),
                "perm_id": getattr(execution, "permId", None),
                "client_id": getattr(execution, "clientId", None),
                "account": mask_account(getattr(execution, "acctNumber", None)),

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
                    0.0
                ),

                "price":
                safe_float(
                    getattr(
                        execution,
                        "price",
                        None
                    ),
                    0.0
                ),

                "time":
                getattr(
                    execution,
                    "time",
                    None
                )
            })


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

            "client_id":
            config.get(
                "client_id"
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

        app.reqOpenOrders()

        app.reqExecutions(8302, ExecutionFilter())

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
                and app.executions_event.is_set()
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

            "execution_rows": app.execution_rows,
            "order_status_rows": app.order_status_rows,

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

                "executions": app.executions_event.is_set()
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
