"""
V7.1 AURORA Position Sizing & Rebalancing Engine

Improvements:
- Whole-share overshoot protection
- Chooses the share quantity closest to target weight
- Manual review for expensive stocks when one share would overshoot
- Calculates projected post-trade position weights
- Calculates estimated cash generated / required
- Calculates projected theme concentration

Important:
- No broker orders are sent.
- Existing account cash is not assumed.
"""

import math
import copy


MAX_POSITION_WEIGHT = 12.0

ADD_HIGH_TARGET = 5.0
ADD_MEDIUM_TARGET = 4.0

REDUCE_HIGH_TARGET = 10.0
REDUCE_MEDIUM_TARGET = 11.0

THEME_CONCENTRATION_LIMIT = 35.0

MIN_TRADE_VALUE = 100.0

MANUAL_REVIEW_EXCESS_WEIGHT = 1.0


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

        total_value += safe_float(
            position.get(
                "current_value",
                0
            )
        )

    return round(
        total_value,
        2
    )


def determine_target_weight(
    portfolio_action,
    conviction,
    current_weight
):

    if portfolio_action == "EXIT":

        return 0.0


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


    if portfolio_action == "ADD":

        if conviction == "HIGH":

            target = ADD_HIGH_TARGET

        else:

            target = ADD_MEDIUM_TARGET


        return min(
            target,
            MAX_POSITION_WEIGHT
        )


    if current_weight > MAX_POSITION_WEIGHT:

        return MAX_POSITION_WEIGHT


    return current_weight


def calculate_weight(
    value,
    portfolio_value
):

    if portfolio_value <= 0:

        return 0.0


    return (
        value
        /
        portfolio_value
        *
        100
    )


def select_best_sell_quantity(
    shares,
    current_price,
    current_value,
    portfolio_value,
    target_weight
):

    target_value = (
        portfolio_value
        *
        target_weight
        /
        100
    )


    value_to_sell = max(
        0,
        current_value
        -
        target_value
    )


    if (
        value_to_sell <= 0
        or current_price <= 0
    ):

        return {

            "shares":
            0,

            "projected_value":
            current_value,

            "projected_weight":
            calculate_weight(
                current_value,
                portfolio_value
            ),

            "ideal_shares":
            0
        }


    ideal_shares = (
        value_to_sell
        /
        current_price
    )


    floor_shares = math.floor(
        ideal_shares
    )


    ceil_shares = math.ceil(
        ideal_shares
    )


    max_shares = int(
        round(
            shares
        )
    )


    candidates = set([

        max(
            0,
            min(
                floor_shares,
                max_shares
            )
        ),

        max(
            0,
            min(
                ceil_shares,
                max_shares
            )
        )

    ])


    best_shares = 0

    best_projected_value = (
        current_value
    )

    best_projected_weight = (
        calculate_weight(
            current_value,
            portfolio_value
        )
    )

    best_distance = abs(
        best_projected_weight
        -
        target_weight
    )


    for candidate in candidates:

        projected_value = max(
            0,
            current_value
            -
            (
                candidate
                *
                current_price
            )
        )


        projected_weight = (
            calculate_weight(
                projected_value,
                portfolio_value
            )
        )


        distance = abs(
            projected_weight
            -
            target_weight
        )


        if distance < best_distance:

            best_distance = (
                distance
            )

            best_shares = (
                candidate
            )

            best_projected_value = (
                projected_value
            )

            best_projected_weight = (
                projected_weight
            )


    return {

        "shares":
        best_shares,

        "projected_value":
        round(
            best_projected_value,
            2
        ),

        "projected_weight":
        round(
            best_projected_weight,
            2
        ),

        "ideal_shares":
        round(
            ideal_shares,
            2
        )
    }


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

            "projected_weight_pct":
            0,

            "reason":
            "Insufficient portfolio or price data"
        }


    current_weight = (
        calculate_weight(
            current_value,
            portfolio_value
        )
    )


    target_weight = (
        determine_target_weight(
            portfolio_action,
            conviction,
            current_weight
        )
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


    trade_action = (
        "NO_TRADE"
    )

    suggested_shares = 0

    suggested_trade_value = 0.0

    projected_value = (
        current_value
    )

    projected_weight = (
        current_weight
    )

    requires_cash = False

    reason = (
        "Position already aligned with target"
    )


    # ==================================================
    # EXIT
    # ==================================================

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


        projected_value = 0

        projected_weight = 0


        trade_action = (
            "SELL_ALL"
        )


        reason = (
            "Portfolio engine recommends full exit"
        )


    # ==================================================
    # REDUCE / CONCENTRATION SELL
    # ==================================================

    elif value_difference < 0:

        value_to_sell = abs(
            value_difference
        )


        if (
            value_to_sell
            >=
            MIN_TRADE_VALUE
        ):

            best_sell = (
                select_best_sell_quantity(
                    shares=shares,
                    current_price=current_price,
                    current_value=current_value,
                    portfolio_value=portfolio_value,
                    target_weight=target_weight
                )
            )


            shares_to_sell = (
                best_sell.get(
                    "shares",
                    0
                )
            )


            ideal_shares = (
                best_sell.get(
                    "ideal_shares",
                    0
                )
            )


            if shares_to_sell > 0:

                suggested_shares = (
                    shares_to_sell
                )


                suggested_trade_value = (
                    shares_to_sell
                    *
                    current_price
                )


                projected_value = (
                    best_sell.get(
                        "projected_value",
                        current_value
                    )
                )


                projected_weight = (
                    best_sell.get(
                        "projected_weight",
                        current_weight
                    )
                )


                trade_action = (
                    "SELL_PARTIAL"
                )


                if portfolio_action == "REDUCE":

                    reason = (
                        "Whole-share quantity selected closest to target weight"
                    )

                else:

                    reason = (
                        "Position reduced toward maximum concentration limit"
                    )


            elif (
                ideal_shares > 0
                and
                (
                    current_weight
                    -
                    target_weight
                )
                >=
                MANUAL_REVIEW_EXCESS_WEIGHT
            ):

                trade_action = (
                    "MANUAL_REVIEW"
                )


                reason = (
                    "One whole share would overshoot target more than holding current position"
                )


    # ==================================================
    # ADD
    # ==================================================

    elif (
        value_difference > 0
        and
        portfolio_action == "ADD"
    ):

        value_to_add = (
            value_difference
        )


        if (
            value_to_add
            >=
            MIN_TRADE_VALUE
        ):

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


                projected_value = (
                    current_value
                    +
                    suggested_trade_value
                )


                projected_weight = (
                    calculate_weight(
                        projected_value,
                        portfolio_value
                    )
                )


                trade_action = (
                    "BUY_TO_TARGET"
                )


                requires_cash = True


                reason = (
                    "Additional capital required to move toward target weight"
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

        "projected_weight_pct":
        round(
            projected_weight,
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

        "projected_value":
        round(
            projected_value,
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


def calculate_theme_exposure(
    portfolio_results,
    portfolio_value,
    plan_lookup=None
):

    theme_values = {}


    if portfolio_value <= 0:

        return {}


    for item in portfolio_results:

        ticker = item.get(
            "ticker",
            "UNKNOWN"
        )


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


        value = safe_float(
            position.get(
                "current_value",
                0
            )
        )


        if plan_lookup:

            plan = plan_lookup.get(
                ticker
            )

            if plan:

                value = safe_float(
                    plan.get(
                        "projected_value",
                        value
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
            value
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
                if weight
                >=
                THEME_CONCENTRATION_LIMIT
                else
                "NORMAL"
            )
        }


    return exposure


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
        6,

        "SELL_PARTIAL":
        5,

        "MANUAL_REVIEW":
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


    total_sell_value = sum(

        safe_float(
            plan.get(
                "suggested_trade_value",
                0
            )
        )

        for plan in plans

        if plan.get(
            "trade_action"
        )
        in [
            "SELL_ALL",
            "SELL_PARTIAL"
        ]

    )


    total_buy_value = sum(

        safe_float(
            plan.get(
                "suggested_trade_value",
                0
            )
        )

        for plan in plans

        if plan.get(
            "trade_action"
        )
        ==
        "BUY_TO_TARGET"

    )


    estimated_net_cash_generated = (
        total_sell_value
        -
        total_buy_value
    )


    plan_lookup = {

        plan.get(
            "ticker"
        ):
        plan

        for plan in plans

    }


    current_theme_exposure = (
        calculate_theme_exposure(
            portfolio_results,
            portfolio_value
        )
    )


    projected_theme_exposure = (
        calculate_theme_exposure(
            portfolio_results,
            portfolio_value,
            plan_lookup=plan_lookup
        )
    )


    concentration_alerts = []


    for theme, data in projected_theme_exposure.items():

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

                "projected_weight_pct":
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
        "V7.1 Position Sizing & Rebalancing Engine",

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

        "estimated_sell_proceeds":
        round(
            total_sell_value,
            2
        ),

        "estimated_buy_requirement":
        round(
            total_buy_value,
            2
        ),

        "estimated_net_cash_generated":
        round(
            estimated_net_cash_generated,
            2
        ),

        "current_theme_exposure":
        current_theme_exposure,

        "projected_theme_exposure":
        projected_theme_exposure,

        "concentration_alerts":
        concentration_alerts,

        "rebalancing_plan":
        plans
    }



def apply_event_risk_to_rebalancing(
    rebalancing_result,
    event_risk_result,
    portfolio_results
):
    """
    V7.5 overlay for existing-position ADD trades.

    - BLOCK: cancel BUY_TO_TARGET
    - REDUCE_SIZE: scale BUY_TO_TARGET quantity
    - SELL actions are never blocked by scheduled event risk
    - Recalculate projected values, theme exposure and cash
    """

    adjusted = copy.deepcopy(
        rebalancing_result
        or
        {}
    )

    plans = (
        adjusted.get(
            "rebalancing_plan",
            []
        )
        or
        []
    )

    ticker_risk = (
        (
            event_risk_result
            or
            {}
        ).get(
            "ticker_risk",
            {}
        )
        or
        {}
    )

    portfolio_value = safe_float(
        adjusted.get(
            "portfolio_value",
            0
        )
    )

    for plan in plans:
        if plan.get(
            "trade_action"
        ) != "BUY_TO_TARGET":
            continue

        ticker = plan.get(
            "ticker"
        )

        risk = (
            ticker_risk.get(
                ticker,
                {}
            )
            or
            {}
        )

        combined = (
            risk.get(
                "combined",
                {}
            )
            or
            {}
        )

        event_policy = combined.get(
            "new_entry_policy",
            "ALLOW"
        )

        multiplier = safe_float(
            combined.get(
                "position_size_multiplier",
                1.0
            ),
            1.0
        )

        plan[
            "event_policy"
        ] = event_policy

        plan[
            "event_risk_level"
        ] = combined.get(
            "risk_level",
            "UNKNOWN"
        )

        plan[
            "event_reasons"
        ] = combined.get(
            "reasons",
            []
        )

        if event_policy == "BLOCK":
            plan[
                "trade_action"
            ] = "EVENT_BLOCK"

            plan[
                "suggested_shares"
            ] = 0

            plan[
                "suggested_trade_value"
            ] = 0.0

            plan[
                "requires_cash"
            ] = False

            plan[
                "projected_value"
            ] = round(
                safe_float(
                    plan.get(
                        "current_value",
                        0
                    )
                ),
                2
            )

            plan[
                "projected_weight_pct"
            ] = round(
                safe_float(
                    plan.get(
                        "current_weight_pct",
                        0
                    )
                ),
                2
            )

            plan[
                "reason"
            ] = (
                "Additional buy blocked by V7.5 scheduled event risk"
            )

            continue

        if (
            event_policy == "REDUCE_SIZE"
            and
            multiplier < 1
        ):
            original_shares = int(
                safe_float(
                    plan.get(
                        "suggested_shares",
                        0
                    )
                )
            )

            if original_shares <= 0:
                continue

            reduced_shares = math.floor(
                original_shares
                *
                max(
                    0,
                    multiplier
                )
            )

            current_value = safe_float(
                plan.get(
                    "current_value",
                    0
                )
            )

            original_trade_value = safe_float(
                plan.get(
                    "suggested_trade_value",
                    0
                )
            )

            implied_price = (
                original_trade_value
                /
                original_shares
                if original_shares > 0
                else 0
            )

            if reduced_shares <= 0:
                plan[
                    "trade_action"
                ] = "EVENT_BLOCK"

                plan[
                    "suggested_shares"
                ] = 0

                plan[
                    "suggested_trade_value"
                ] = 0.0

                plan[
                    "requires_cash"
                ] = False

                plan[
                    "projected_value"
                ] = round(
                    current_value,
                    2
                )

                plan[
                    "projected_weight_pct"
                ] = round(
                    calculate_weight(
                        current_value,
                        portfolio_value
                    ),
                    2
                )

                plan[
                    "reason"
                ] = (
                    "Event-risk size reduction leaves no executable whole-share add"
                )

                continue

            reduced_trade_value = (
                reduced_shares
                *
                implied_price
            )

            projected_value = (
                current_value
                +
                reduced_trade_value
            )

            plan[
                "suggested_shares"
            ] = reduced_shares

            plan[
                "suggested_trade_value"
            ] = round(
                reduced_trade_value,
                2
            )

            plan[
                "projected_value"
            ] = round(
                projected_value,
                2
            )

            plan[
                "projected_weight_pct"
            ] = round(
                calculate_weight(
                    projected_value,
                    portfolio_value
                ),
                2
            )

            plan[
                "reason"
            ] = (
                "Additional buy reduced by V7.5 scheduled event risk"
            )

    priority = {
        "SELL_ALL": 7,
        "SELL_PARTIAL": 6,
        "EVENT_BLOCK": 5,
        "MANUAL_REVIEW": 4,
        "BUY_TO_TARGET": 3,
        "NO_TRADE": 1
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

    total_sell_value = sum(
        safe_float(
            plan.get(
                "suggested_trade_value",
                0
            )
        )
        for plan in plans
        if plan.get(
            "trade_action"
        )
        in [
            "SELL_ALL",
            "SELL_PARTIAL"
        ]
    )

    total_buy_value = sum(
        safe_float(
            plan.get(
                "suggested_trade_value",
                0
            )
        )
        for plan in plans
        if plan.get(
            "trade_action"
        )
        ==
        "BUY_TO_TARGET"
    )

    adjusted[
        "estimated_sell_proceeds"
    ] = round(
        total_sell_value,
        2
    )

    adjusted[
        "estimated_buy_requirement"
    ] = round(
        total_buy_value,
        2
    )

    adjusted[
        "estimated_net_cash_generated"
    ] = round(
        total_sell_value
        -
        total_buy_value,
        2
    )

    plan_lookup = {
        plan.get(
            "ticker"
        ):
        plan
        for plan in plans
    }

    projected_theme_exposure = (
        calculate_theme_exposure(
            portfolio_results,
            portfolio_value,
            plan_lookup=plan_lookup
        )
    )

    adjusted[
        "projected_theme_exposure"
    ] = projected_theme_exposure

    concentration_alerts = []

    for theme, data in (
        projected_theme_exposure.items()
    ):
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

                "projected_weight_pct":
                data.get(
                    "weight_pct"
                ),

                "limit_pct":
                THEME_CONCENTRATION_LIMIT,

                "status":
                "HIGH_CONCENTRATION"
            })

    adjusted[
        "concentration_alerts"
    ] = concentration_alerts

    adjusted[
        "event_risk_overlay"
    ] = {
        "engine":
        "V7.5 Existing Position Event-Risk Overlay",

        "applied":
        True,

        "blocked_add_count":
        len([
            plan
            for plan in plans
            if plan.get(
                "trade_action"
            )
            ==
            "EVENT_BLOCK"
        ]),

        "reduced_add_count":
        len([
            plan
            for plan in plans
            if (
                plan.get(
                    "trade_action"
                )
                ==
                "BUY_TO_TARGET"
                and
                plan.get(
                    "event_policy"
                )
                ==
                "REDUCE_SIZE"
            )
        ])
    }

    return adjusted
