"""AURORA V8.9.6 dry-run execution gate.

This engine produces shadow orders only. It has no broker dependency and
contains no broker submission path. Every decision fails closed unless the
runtime is DRY_RUN and all pre-trade controls pass.
"""

from datetime import datetime, timezone
import math
import os
import uuid

from engines.aurora_run_mode_engine import load_run_mode
from engines.market_data_quality_gate import (
    evaluate_market_data_for_execution,
)


DEFAULT_MAX_ORDER_NOTIONAL_USD = 100.0
DEFAULT_MAX_DAILY_GROSS_NOTIONAL_USD = 500.0
DEFAULT_MAX_SPREAD_BPS = 50.0
DEFAULT_MAX_LIMIT_DEVIATION_BPS = 50.0


def _env_float(name, default):
    raw = os.getenv(name)
    if raw is None:
        return float(default)
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return float(default)

    if not math.isfinite(value) or value <= 0:
        return float(default)

    return value


class DryRunExecutionEngine:
    def __init__(self):
        self.shadow_orders = {}
        self.seen_idempotency_keys = set()
        self.daily_gross_notional_usd = 0.0

    def _block(self, reason, **extra):
        return {
            "status": "BLOCKED",
            "reason": reason,
            "broker_submission_allowed": False,
            "paper_order_submission_allowed": False,
            "live_execution_allowed": False,
            **extra,
        }

    def evaluate_and_create_shadow_order(
        self,
        order_intent,
        market_data,
    ):
        order_intent = order_intent or {}
        market_data = market_data or {}

        run_mode = load_run_mode()
        if run_mode.get("mode") != "DRY_RUN":
            return self._block(
                "DRY_RUN_MODE_REQUIRED",
                run_mode=run_mode.get("mode"),
            )

        symbol = str(order_intent.get("symbol") or "").strip().upper()
        asset_type = str(
            order_intent.get("asset_type") or ""
        ).strip().upper()
        action = str(order_intent.get("action") or "").strip().upper()
        order_type = str(
            order_intent.get("order_type") or ""
        ).strip().upper()
        time_in_force = str(
            order_intent.get("time_in_force") or ""
        ).strip().upper()
        risk_approval = str(
            order_intent.get("risk_approval") or ""
        ).strip().upper()
        idempotency_key = str(
            order_intent.get("idempotency_key") or ""
        ).strip()

        raw_quantity = order_intent.get("quantity")
        try:
            quantity_float = float(raw_quantity)
        except (TypeError, ValueError):
            quantity_float = 0.0

        quantity_is_whole = (
            math.isfinite(quantity_float)
            and quantity_float > 0
            and quantity_float.is_integer()
        )
        quantity = int(quantity_float) if quantity_is_whole else 0

        try:
            limit_price = float(order_intent.get("limit_price") or 0)
        except (TypeError, ValueError):
            limit_price = 0.0

        if not math.isfinite(limit_price):
            limit_price = 0.0

        try:
            current_position_float = float(
                order_intent.get("current_position_qty") or 0
            )
        except (TypeError, ValueError):
            current_position_float = 0.0

        current_position_qty = (
            int(current_position_float)
            if (
                math.isfinite(current_position_float)
                and current_position_float >= 0
                and current_position_float.is_integer()
            )
            else 0
        )

        if not symbol:
            return self._block("SYMBOL_REQUIRED")

        if asset_type != "STK":
            return self._block(
                "STOCKS_ONLY",
                asset_type=asset_type or None,
            )

        if action not in {"BUY", "SELL"}:
            return self._block(
                "BUY_OR_SELL_REQUIRED",
                action=action or None,
            )

        if order_type != "LIMIT":
            return self._block(
                "LIMIT_ORDERS_ONLY",
                order_type=order_type or None,
            )

        if time_in_force != "DAY":
            return self._block(
                "DAY_TIF_REQUIRED",
                time_in_force=time_in_force or None,
            )

        if risk_approval != "APPROVED":
            return self._block("RISK_APPROVAL_REQUIRED")

        if not quantity_is_whole:
            return self._block(
                "WHOLE_POSITIVE_SHARE_QUANTITY_REQUIRED"
            )

        if limit_price <= 0:
            return self._block("POSITIVE_LIMIT_PRICE_REQUIRED")

        if not idempotency_key:
            return self._block("IDEMPOTENCY_KEY_REQUIRED")

        if idempotency_key in self.seen_idempotency_keys:
            return self._block(
                "DUPLICATE_ORDER_INTENT",
                idempotency_key=idempotency_key,
            )

        if action == "SELL" and current_position_qty < quantity:
            return self._block(
                "SHORT_SELLING_DISABLED",
                current_position_qty=current_position_qty,
            )

        market_gate = evaluate_market_data_for_execution(
            market_data
        )
        if not market_gate.get("execution_eligible"):
            return self._block(
                "MARKET_DATA_GATE_BLOCKED",
                market_data_gate=market_gate,
            )

        try:
            bid = float(market_data.get("bid") or 0)
            ask = float(market_data.get("ask") or 0)
        except (TypeError, ValueError):
            bid = 0.0
            ask = 0.0

        if not math.isfinite(bid):
            bid = 0.0
        if not math.isfinite(ask):
            ask = 0.0

        if bid <= 0 or ask <= 0 or ask < bid:
            return self._block(
                "VALID_BID_ASK_REQUIRED",
                bid=bid,
                ask=ask,
            )

        midpoint = (bid + ask) / 2.0
        spread_bps = (
            ((ask - bid) / midpoint) * 10000
            if midpoint > 0
            else float("inf")
        )

        max_spread_bps = _env_float(
            "AURORA_DRY_RUN_MAX_SPREAD_BPS",
            DEFAULT_MAX_SPREAD_BPS,
        )
        if spread_bps > max_spread_bps:
            return self._block(
                "SPREAD_LIMIT_EXCEEDED",
                spread_bps=round(spread_bps, 3),
                max_spread_bps=max_spread_bps,
            )

        max_limit_deviation_bps = _env_float(
            "AURORA_DRY_RUN_MAX_LIMIT_DEVIATION_BPS",
            DEFAULT_MAX_LIMIT_DEVIATION_BPS,
        )
        if action == "BUY":
            limit_reference_price = ask
            limit_deviation_bps = max(
                0.0,
                ((limit_price - ask) / ask) * 10000,
            )
        else:
            limit_reference_price = bid
            limit_deviation_bps = max(
                0.0,
                ((bid - limit_price) / bid) * 10000,
            )

        if limit_deviation_bps > max_limit_deviation_bps:
            return self._block(
                "LIMIT_PRICE_DEVIATION_EXCEEDED",
                action=action,
                limit_price=round(limit_price, 4),
                limit_reference_price=round(limit_reference_price, 4),
                limit_deviation_bps=round(limit_deviation_bps, 3),
                max_limit_deviation_bps=max_limit_deviation_bps,
            )

        notional = quantity * limit_price
        max_order_notional = _env_float(
            "AURORA_DRY_RUN_MAX_ORDER_NOTIONAL_USD",
            DEFAULT_MAX_ORDER_NOTIONAL_USD,
        )
        if notional > max_order_notional:
            return self._block(
                "ORDER_NOTIONAL_LIMIT_EXCEEDED",
                order_notional_usd=round(notional, 2),
                max_order_notional_usd=max_order_notional,
            )

        max_daily_gross = _env_float(
            "AURORA_DRY_RUN_MAX_DAILY_GROSS_NOTIONAL_USD",
            DEFAULT_MAX_DAILY_GROSS_NOTIONAL_USD,
        )
        projected_daily_gross = (
            self.daily_gross_notional_usd + notional
        )
        if projected_daily_gross > max_daily_gross:
            return self._block(
                "DAILY_GROSS_NOTIONAL_LIMIT_EXCEEDED",
                projected_daily_gross_notional_usd=round(
                    projected_daily_gross,
                    2,
                ),
                max_daily_gross_notional_usd=max_daily_gross,
            )

        shadow_order_id = str(uuid.uuid4())
        shadow_order = {
            "shadow_order_id": shadow_order_id,
            "idempotency_key": idempotency_key,
            "symbol": symbol,
            "asset_type": asset_type,
            "action": action,
            "quantity": quantity,
            "order_type": order_type,
            "time_in_force": time_in_force,
            "limit_price": round(limit_price, 4),
            "order_notional_usd": round(notional, 2),
            "spread_bps": round(spread_bps, 3),
            "limit_reference_price": round(limit_reference_price, 4),
            "limit_deviation_bps": round(limit_deviation_bps, 3),
            "max_limit_deviation_bps": max_limit_deviation_bps,
            "market_data_gate": market_gate,
            "status": "SHADOW_ACCEPTED",
            "broker_submission_allowed": False,
            "paper_order_submission_allowed": False,
            "live_execution_allowed": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        self.shadow_orders[shadow_order_id] = shadow_order
        self.seen_idempotency_keys.add(idempotency_key)
        self.daily_gross_notional_usd = projected_daily_gross

        return shadow_order

    def submit_to_broker(self, *args, **kwargs):
        raise RuntimeError(
            "DRY_RUN_BROKER_SUBMISSION_HARD_BLOCKED"
        )

    def generate_report(self):
        return {
            "engine": "AURORA V8.9.6 Dry-Run Execution Gate",
            "mode": load_run_mode().get("mode"),
            "shadow_order_count": len(self.shadow_orders),
            "daily_gross_notional_usd": round(
                self.daily_gross_notional_usd,
                2,
            ),
            "broker_submission_allowed": False,
            "paper_order_submission_allowed": False,
            "live_execution_allowed": False,
            "shadow_orders": self.shadow_orders,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
