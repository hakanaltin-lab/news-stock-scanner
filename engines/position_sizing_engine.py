"""
V7.0 AURORA Position Sizing & Rebalancing Engine

Purpose:
- Calculate current portfolio weights
- Convert portfolio actions into sizing recommendations
- Suggest shares to BUY / SELL / EXIT
- Control single-position concentration
- Monitor theme concentration

Important:
- This engine does NOT assume available cash.
- BUY recommendations show capital required to reach target.
- Calculations are based on the current portfolio snapshot.
"""

import math


MAX_POSITION_WEIGHT = 12.0

ADD_HIGH_TARGET = 5.0
ADD_MEDIUM_TARGET = 4.0

REDUCE_HIGH_TARGET = 10.0
REDUCE_MEDIUM_TARGET = 11.0

THEME_CONCENTRATION_LIMIT = 35.0

MIN_TRADE_VALUE = 100.0


def safe_float(
    value,
    default=0.0
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


def calculate_portfolio_value(
    portfolio_results
):

    total_value = 0.0

    for item in portfolio_results:

        management = item.get(
            "portfolio_management",
            {}
        )

        position = management.get(
            "position",
            {}
        )

        current_value = safe_float(
            position.get(
                "current_value",
                0
            )
        )

        total_value += current_value

    return round(
        total_value,
        2
    )


def calculate_theme_exposure(
    portfolio_results,
    portfolio_value
):

    theme_values = {}

    if portfolio_value <= 0:

        return {}


    for item in portfolio_results:

        holding = item.get(
            "holding",
            {}
        )

        theme = holding.get(
            "theme"
        ) or "Unknown"


        management = item.get(
            "portfolio_management",
            {}
        )

        position = management.get(
            "position",
            {}
        )


        current_value = safe_float(
            position.get(
                "current_value",
                0
            )
        )


        theme_values[
            theme
        ] = (
            theme_values.get(
                theme,
                0
            )
            +
            current_value
        )


    exposure = {}


    for theme, value in theme_values.items():

        weight = (
            value
            /
            portfolio_value
            *
            100
        )


        exposure[
            theme
        ] = {

            "value":
            round(
                value,
                2
            ),

            "weight_pct":
            round(
                weight,
                2
            ),

            "concentration_status":
            (
                "HIGH"
                if weight >= THEME_CONCENTRATION_LIMIT
                else "NORMAL"
            )
        }


    return exposure


def determine_target_weight(
    portfolio_action,
    conviction,
    current_weight
):

    # ==========================================
    # EXIT
    # ==========================================

    if portfolio_action == "EXIT":

        return 0.0


    # ==========================================
    # REDUCE
    # ==========================================

    if portfolio_action == "REDUCE":

        if conviction == "HIGH":

            return min(
                current_weight,
                REDUCE_HIGH_TARGET
            )


        return min(
            current_weight,
            REDUCE_MEDIUM_TARGET
        )


    # ==========================================
    # ADD
    # ==========================================

    if portfolio_action == "ADD":

        if conviction == "HIGH":

            target = ADD_HIGH_TARGET

        else:

            target = ADD_MEDIUM_TARGET


        return min(
            target,
            MAX_POSITION_WEIGHT
        )


    # ==========================================
    # HOLD / WATCH
    # Concentration overlay
    # ==========================================

    if current_weight > MAX_POSITION_WEIGHT:

        return MAX_POSITION_WEIGHT


    return current_weight


def calculate_trade_plan(
    ticker,
    shares,
    current_price,
    current_value,
    portfolio_value,
    portfolio_action,
    conviction
):

    shares = safe_float(
        shares
    )

    current_price = safe_float(
        current_price
    )

    current_value = safe_float(
        current_value
    )


    if (
        portfolio_value <= 0
        or current_price <= 0
    ):

        return {

            "ticker":
            ticker,

            "trade_action":
            "NO_TRADE",

            "suggested_shares":
            0,

            "suggested_trade_value":
            0,

            "current_weight_pct":
            0,

            "target_weight_pct":
            0,

            "reason":
            "Insufficient portfolio or price data"
        }


    current_weight = (
        current_value
        /
        portfolio_value
        *
        100
    )


    target_weight = determine_target_weight(
        portfolio_action,
        conviction,
        current_weight
    )


    target_value = (
        portfolio_value
        *
        target_weight
        /
        100
    )


    value_difference = (
        target_value
        -
        current_value
    )


    trade_action = "NO_TRADE"

    suggested_shares = 0

    suggested_trade_value = 0.0

    requires_cash = False

    reason = (
        "Position already aligned with target"
    )


    # ==========================================
    # EXIT
    # ==========================================

    if portfolio_action == "EXIT":

        suggested_shares = int(
            round(
                shares
            )
        )

        suggested_trade_value = (
            suggested_shares
            *
            current_price
        )

        trade_action = "SELL_ALL"

        reason = (
            "Portfolio engine recommends full exit"
        )


    # ==========================================
    # SELL / REDUCE
    # ==========================================

    elif value_difference < 0:

        value_to_sell = abs(
            value_difference
        )


        if value_to_sell >= MIN_TRADE_VALUE:

            shares_to_sell = math.ceil(
                value_to_sell
                /
                current_price
            )


            shares_to_sell = min(
                shares_to_sell,
                int(
                    round(
                        shares
                    )
                )
            )


            suggested_shares = (
                shares_to_sell
            )


            suggested_trade_value = (
                shares_to_sell
                *
                current_price
            )


            trade_action = (
                "SELL_PARTIAL"
            )


            if portfolio_action == "REDUCE":

                reason = (
                    "Reduce exposure toward V7.0 target weight"
                )

            else:

                reason = (
                    "Position exceeds maximum concentration limit"
                )


    # ==========================================
    # BUY / ADD
    # ==========================================

    elif (
        value_difference > 0
        and portfolio_action == "ADD"
    ):

        value_to_add = (
            value_difference
        )


        if value_to_add >= MIN_TRADE_VALUE:

            shares_to_buy = math.floor(
                value_to_add
                /
                current_price
            )


            if shares_to_buy > 0:

                suggested_shares = (
                    shares_to_buy
                )


                suggested_trade_value = (
                    shares_to_buy
                    *
                    current_price
                )


                trade_action = (
                    "BUY_TO_TARGET"
                )


                requires_cash = True


                reason = (
                    "Additional capital required to reach target weight"
                )


    return {

        "ticker":
        ticker,

        "base_action":
        portfolio_action,

        "conviction":
        conviction,

        "current_weight_pct":
        round(
            current_weight,
            2
        ),

        "target_weight_pct":
        round(
            target_weight,
            2
        ),

        "current_value":
        round(
            current_value,
            2
        ),

        "target_value":
        round(
            target_value,
            2
        ),

        "trade_action":
        trade_action,

        "suggested_shares":
        suggested_shares,

        "suggested_trade_value":
        round(
            suggested_trade_value,
            2
        ),

        "requires_cash":
        requires_cash,

        "reason":
        reason
    }


def build_rebalancing_plan(
    portfolio_results
):

    portfolio_value = (
        calculate_portfolio_value(
            portfolio_results
        )
    )


    plans = []


    for item in portfolio_results:

        ticker = item.get(
            "ticker",
            "UNKNOWN"
        )


        management = item.get(
            "portfolio_management",
            {}
        )


        position = management.get(
            "position",
            {}
        )


        portfolio_action = item.get(
            "portfolio_action",
            "WATCH"
        )


        conviction = management.get(
            "conviction",
            "LOW"
        )


        plan = calculate_trade_plan(

            ticker=ticker,

            shares=position.get(
                "shares",
                0
            ),

            current_price=position.get(
                "current_price",
                0
            ),

            current_value=position.get(
                "current_value",
                0
            ),

            portfolio_value=portfolio_value,

            portfolio_action=portfolio_action,

            conviction=conviction

        )


        plans.append(
            plan
        )


    priority = {

        "SELL_ALL":
        5,

        "SELL_PARTIAL":
        4,

        "BUY_TO_TARGET":
        3,

        "NO_TRADE":
        1

    }


    plans.sort(

        key=lambda item:

        priority.get(
            item.get(
                "trade_action"
            ),
            0
        ),

        reverse=True

    )


    theme_exposure = (
        calculate_theme_exposure(
            portfolio_results,
            portfolio_value
        )
    )


    concentration_alerts = []


    for theme, data in theme_exposure.items():

        if (
            data.get(
                "concentration_status"
            )
            ==
            "HIGH"
        ):

            concentration_alerts.append({

                "theme":
                theme,

                "weight_pct":
                data.get(
                    "weight_pct"
                ),

                "limit_pct":
                THEME_CONCENTRATION_LIMIT,

                "status":
                "HIGH_CONCENTRATION"

            })


    return {

        "engine":
        "V7.0 Position Sizing & Rebalancing Engine",

        "portfolio_value":
        portfolio_value,

        "position_count":
        len(
            portfolio_results
        ),

        "max_position_weight_pct":
        MAX_POSITION_WEIGHT,

        "theme_concentration_limit_pct":
        THEME_CONCENTRATION_LIMIT,

        "theme_exposure":
        theme_exposure,

        "concentration_alerts":
        concentration_alerts,

        "rebalancing_plan":
        plans
    }
