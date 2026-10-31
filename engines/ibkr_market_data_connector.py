"""AURORA V8.9.7 — IBKR real-time market-data read-only connector.

Purpose
-------
- Obtain a one-shot top-of-book stock quote from IB Gateway Paper.
- Never submit orders.
- Fail closed unless the endpoint is 127.0.0.1:4002 and the managed account
  matches the runtime-only PAPER allowlist.
- Distinguish real-time (marketDataType=1) from delayed/frozen data.
- Mark only verified real-time quotes as execution eligible.

The official IBKR Python TWS API must be installed on the VPS from Interactive
Brokers' official API package. This repository does not install an unofficial
PyPI ibapi package.
"""

from datetime import datetime, timezone
import math
import os
import threading
import time

from engines.ibkr_account_guard import evaluate_paper_account_identity


try:
    from ibapi.client import EClient
    from ibapi.contract import Contract
    from ibapi.wrapper import EWrapper

    IBAPI_AVAILABLE = True
    IBAPI_IMPORT_ERROR = None

except Exception as error:
    EClient = object
    EWrapper = object
    Contract = object

    IBAPI_AVAILABLE = False
    IBAPI_IMPORT_ERROR = str(error)


ENGINE_VERSION = "V8.9.7 IBKR Market Data Connector"
LIVE_EXECUTION_ALLOWED = False
PAPER_ORDER_SUBMISSION_ALLOWED = False

MARKET_DATA_TYPES = {
    1: "REALTIME",
    2: "FROZEN",
    3: "DELAYED",
    4: "DELAYED_FROZEN",
}

LIVE_TICK_PRICE_TYPES = {
    1: "bid",
    2: "ask",
    4: "last_price",
}

DELAYED_TICK_PRICE_TYPES = {
    66: "bid",
    67: "ask",
    68: "last_price",
}


def _env_bool(name, default=False):
    raw = os.getenv(name)
    if raw is None:
        return default
    return str(raw).strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def load_ibkr_market_data_config():
    try:
        port = int(os.getenv("AURORA_IBKR_PORT", "4002"))
    except Exception:
        port = 4002

    try:
        client_id = int(
            os.getenv(
                "AURORA_IBKR_MARKET_DATA_CLIENT_ID",
                "83",
            )
        )
    except Exception:
        client_id = 83

    try:
        timeout_seconds = float(
            os.getenv(
                "AURORA_IBKR_MARKET_DATA_TIMEOUT_SECONDS",
                "8",
            )
        )
    except Exception:
        timeout_seconds = 8.0

    mode = os.getenv(
        "AURORA_IBKR_MODE",
        "PAPER",
    ).strip().upper()

    host = os.getenv(
        "AURORA_IBKR_HOST",
        "127.0.0.1",
    ).strip()

    endpoint_safe = (
        mode == "PAPER"
        and host == "127.0.0.1"
        and port == 4002
    )

    return {
        "enabled": _env_bool(
            "AURORA_IBKR_MARKET_DATA_ENABLED",
            False,
        ),
        "mode": mode,
        "host": host,
        "port": port,
        "client_id": client_id,
        "timeout_seconds": max(
            2.0,
            min(timeout_seconds, 30.0),
        ),
        "endpoint_safe": endpoint_safe,
        "live_execution_allowed": False,
        "paper_order_submission_allowed": False,
    }


def _finite_positive(value):
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None

    if not math.isfinite(parsed) or parsed <= 0:
        return None

    return parsed


def _normalized_market_timestamp(value):
    if value is None:
        return None

    if isinstance(value, (int, float)):
        try:
            parsed = datetime.fromtimestamp(
                float(value),
                tz=timezone.utc,
            )
        except (OverflowError, OSError, ValueError):
            return None
    else:
        text = str(value).strip()
        if not text:
            return None
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            return None
        if parsed.tzinfo is None:
            return None
        parsed = parsed.astimezone(timezone.utc)

    return parsed.isoformat()


def evaluate_ibkr_quote_snapshot(raw_quote):
    raw_quote = raw_quote or {}

    data_type_id = raw_quote.get("market_data_type")
    data_type_name = MARKET_DATA_TYPES.get(
        data_type_id,
        "UNKNOWN",
    )

    bid = _finite_positive(raw_quote.get("bid"))
    ask = _finite_positive(raw_quote.get("ask"))
    last_price = _finite_positive(
        raw_quote.get("last_price")
    )

    bid_ask_valid = (
        bid is not None
        and ask is not None
        and ask >= bid
    )

    quote_complete = (
        bid_ask_valid
        and last_price is not None
    )

    realtime_verified = data_type_id == 1
    market_timestamp = _normalized_market_timestamp(
        raw_quote.get("market_timestamp")
    )
    broker_timestamp_verified = market_timestamp is not None

    execution_eligible = (
        realtime_verified
        and quote_complete
        and broker_timestamp_verified
    )

    failure_reasons = []

    if not realtime_verified:
        failure_reasons.append(
            "REALTIME_MARKET_DATA_REQUIRED"
        )

    if not bid_ask_valid:
        failure_reasons.append(
            "VALID_BID_ASK_REQUIRED"
        )

    if last_price is None:
        failure_reasons.append(
            "VALID_LAST_PRICE_REQUIRED"
        )

    if not broker_timestamp_verified:
        failure_reasons.append(
            "BROKER_MARKET_TIMESTAMP_REQUIRED"
        )

    received_at = raw_quote.get(
        "received_at"
    ) or datetime.now(timezone.utc).isoformat()

    return {
        "symbol": raw_quote.get("symbol"),
        "source": (
            "IBKR_REALTIME"
            if realtime_verified
            else "IBKR_NON_REALTIME"
        ),
        "market_data_type": data_type_id,
        "market_data_type_name": data_type_name,
        "bid": bid,
        "ask": ask,
        "last_price": last_price,
        "market_timestamp": market_timestamp,
        "retrieved_at": received_at,
        "broker_market_timestamp_verified": broker_timestamp_verified,
        "data_points": 1 if quote_complete else 0,
        "data_quality": (
            "AVAILABLE"
            if quote_complete
            else "INCOMPLETE"
        ),
        "execution_eligible": execution_eligible,
        "failure_reasons": failure_reasons,
        "live_execution_allowed": False,
        "paper_order_submission_allowed": False,
    }


if IBAPI_AVAILABLE:

    class _IBKRMarketDataApp(EWrapper, EClient):
        def __init__(self):
            EWrapper.__init__(self)
            EClient.__init__(self, self)

            self.accounts = []
            self.errors = []
            self.connected_event = threading.Event()
            self.accounts_event = threading.Event()
            self.quote_event = threading.Event()
            self.snapshot_end_event = threading.Event()
            self.last_trade_event = threading.Event()

            self.market_data_type_id = None
            self.last_trade_timestamp = None
            self.quote = {
                "bid": None,
                "ask": None,
                "last_price": None,
            }

        def nextValidId(self, orderId):
            self.connected_event.set()

        def managedAccounts(self, accountsList):
            self.accounts = [
                item.strip()
                for item in str(accountsList).split(",")
                if item.strip()
            ]
            self.accounts_event.set()

        def marketDataType(self, reqId, marketDataType):
            self.market_data_type_id = marketDataType

        def tickPrice(self, reqId, tickType, price, attrib):
            field = LIVE_TICK_PRICE_TYPES.get(tickType)
            if field is None:
                field = DELAYED_TICK_PRICE_TYPES.get(tickType)

            if field is not None:
                parsed = _finite_positive(price)
                if parsed is not None:
                    self.quote[field] = parsed

            if all(
                self.quote.get(name) is not None
                for name in ("bid", "ask", "last_price")
            ):
                self.quote_event.set()

        def tickSnapshotEnd(self, reqId):
            self.snapshot_end_event.set()

        def tickByTickAllLast(
            self,
            reqId,
            tickType,
            timestamp,
            price,
            size,
            tickAttribLast,
            exchange,
            specialConditions,
        ):
            market_timestamp = _normalized_market_timestamp(
                timestamp
            )
            parsed_price = _finite_positive(price)

            if (
                market_timestamp is not None
                and parsed_price is not None
            ):
                self.last_trade_timestamp = market_timestamp
                self.quote["last_price"] = parsed_price
                self.last_trade_event.set()

        def error(
            self,
            reqId,
            errorCode,
            errorString,
            advancedOrderRejectJson="",
        ):
            self.errors.append({
                "req_id": reqId,
                "code": errorCode,
                "message": str(errorString)[:240],
            })


def _build_us_stock_contract(symbol):
    contract = Contract()
    contract.symbol = symbol
    contract.secType = "STK"
    contract.exchange = "SMART"
    contract.currency = "USD"
    return contract


def get_ibkr_realtime_quote(symbol):
    symbol = str(symbol or "").strip().upper()
    config = load_ibkr_market_data_config()

    base = {
        "engine": ENGINE_VERSION,
        "symbol": symbol or None,
        "status": "BLOCKED",
        "connection_status": "NOT_ATTEMPTED",
        "config": {
            "enabled": config["enabled"],
            "mode": config["mode"],
            "host": config["host"],
            "port": config["port"],
            "client_id": config["client_id"],
            "endpoint_safe": config["endpoint_safe"],
            "live_execution_allowed": False,
            "paper_order_submission_allowed": False,
        },
    }

    if not symbol:
        return {
            **base,
            "reason": "SYMBOL_REQUIRED",
        }

    if not config["enabled"]:
        return {
            **base,
            "status": "DISABLED",
            "reason": "IBKR_MARKET_DATA_CONNECTOR_DISABLED",
        }

    if not config["endpoint_safe"]:
        return {
            **base,
            "reason": (
                "CONFIG_SAFETY_BLOCK: market-data access is "
                "restricted to PAPER 127.0.0.1:4002."
            ),
        }

    if not IBAPI_AVAILABLE:
        return {
            **base,
            "reason": "OFFICIAL_IBKR_API_NOT_AVAILABLE",
            "ibapi_import_error_present": bool(
                IBAPI_IMPORT_ERROR
            ),
        }

    app = _IBKRMarketDataApp()
    thread = None
    request_id = None
    tick_request_id = None

    try:
        app.connect(
            config["host"],
            config["port"],
            clientId=config["client_id"],
        )

        thread = threading.Thread(
            target=app.run,
            daemon=True,
        )
        thread.start()

        if not app.connected_event.wait(
            config["timeout_seconds"]
        ):
            return {
                **base,
                "status": "CONNECTION_FAILED",
                "connection_status": "TIMEOUT",
                "reason": "IBKR_CONNECTION_TIMEOUT",
            }

        app.reqManagedAccts()

        if not app.accounts_event.wait(
            config["timeout_seconds"]
        ):
            return {
                **base,
                "status": "BLOCKED",
                "connection_status": "CONNECTED",
                "reason": "MANAGED_ACCOUNT_TIMEOUT",
            }

        account_guard = evaluate_paper_account_identity(
            app.accounts
        )

        if not account_guard.get(
            "paper_account_verified"
        ):
            return {
                **base,
                "status": "BLOCKED",
                "connection_status": "CONNECTED",
                "reason": account_guard.get(
                    "reason",
                    "PAPER_ACCOUNT_NOT_VERIFIED",
                ),
                "paper_account_guard": account_guard,
            }

        request_id = 91001
        tick_request_id = 91002
        contract = _build_us_stock_contract(symbol)

        app.reqMarketDataType(1)
        app.reqMktData(
            request_id,
            contract,
            "",
            True,
            False,
            [],
        )
        app.reqTickByTickData(
            tick_request_id,
            contract,
            "AllLast",
            1,
            False,
        )

        deadline = (
            time.monotonic()
            + config["timeout_seconds"]
        )

        while time.monotonic() < deadline:
            quote_snapshot_complete = (
                app.quote_event.is_set()
                or app.snapshot_end_event.is_set()
            )
            if (
                quote_snapshot_complete
                and app.last_trade_event.is_set()
            ):
                break
            time.sleep(0.05)

        received_at = (
            datetime.now(timezone.utc).isoformat()
        )

        evaluated = evaluate_ibkr_quote_snapshot({
            "symbol": symbol,
            "market_data_type": (
                app.market_data_type_id
            ),
            "bid": app.quote.get("bid"),
            "ask": app.quote.get("ask"),
            "last_price": app.quote.get(
                "last_price"
            ),
            "market_timestamp": app.last_trade_timestamp,
            "received_at": received_at,
        })

        status = (
            "REALTIME_READY"
            if evaluated["execution_eligible"]
            else "NON_EXECUTION_DATA"
        )

        return {
            **base,
            "status": status,
            "connection_status": "CONNECTED",
            "reason": (
                "REALTIME_QUOTE_VERIFIED"
                if evaluated["execution_eligible"]
                else "QUOTE_NOT_EXECUTION_ELIGIBLE"
            ),
            "paper_account_guard": account_guard,
            "quote": evaluated,
            "error_count": len(app.errors),
            "errors": app.errors[-5:],
        }

    except Exception as error:
        return {
            **base,
            "status": "ERROR",
            "connection_status": "FAILED",
            "reason": "IBKR_MARKET_DATA_EXCEPTION",
            "error_type": type(error).__name__,
        }

    finally:
        try:
            if IBAPI_AVAILABLE and app.isConnected():
                if request_id is not None:
                    try:
                        app.cancelMktData(request_id)
                    except Exception:
                        pass
                if tick_request_id is not None:
                    try:
                        app.cancelTickByTickData(tick_request_id)
                    except Exception:
                        pass
                app.disconnect()
        except Exception:
            pass
