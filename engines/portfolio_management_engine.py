"""
V6.9 AURORA Portfolio Management Engine

Purpose:
- Manage positions already owned
- Combine cost basis with current AURORA intelligence
- Calculate unrealized P&L
- Produce position-specific actions

Actions:
ADD
HOLD
WATCH
REDUCE
EXIT
"""


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


def calculate_position_metrics(
    shares,
    avg_cost,
    current_price
):

    shares = safe_float(
        shares
    )

    avg_cost = safe_float(
        avg_cost
    )

    current_price = safe_float(
        current_price
    )


    cost_basis = (
        shares
        * avg_cost
    )


    current_value = (
        shares
        * current_price
    )


    unrealized_pnl = (
        current_value
        - cost_basis
    )


    if cost_basis > 0:

        unrealized_pnl_pct = (
            unrealized_pnl
            / cost_basis
            * 100
        )

    else:

        unrealized_pnl_pct = 0


    return {

        "shares":
        shares,

        "avg_cost":
        round(
            avg_cost,
            2
        ),

        "current_price":
        round(
            current_price,
            2
        ),

        "cost_basis":
        round(
            cost_basis,
            2
        ),

        "current_value":
        round(
            current_value,
            2
        ),

        "unrealized_pnl":
        round(
            unrealized_pnl,
            2
        ),

        "unrealized_pnl_pct":
        round(
            unrealized_pnl_pct,
            2
        )
    }


def evaluate_portfolio_position(
    ticker,
    shares,
    avg_cost,
    current_price,
    alpha_score,
    market_score,
    catalyst_score,
    sector_score,
    risk_score,
    signal
):

    metrics = calculate_position_metrics(
        shares,
        avg_cost,
        current_price
    )


    pnl_pct = metrics.get(
        "unrealized_pnl_pct",
        0
    )


    action = "WATCH"

    conviction = "MEDIUM"

    urgency = "LOW"

    reasons = []


    # ==============================================
    # 1. EXIT
    # Severe deterioration + losing position
    # ==============================================

    if (
        alpha_score < 40
        and market_score < 25
        and pnl_pct < 0
    ):

        action = "EXIT"

        conviction = "HIGH"

        urgency = "HIGH"

        reasons = [
            "Alpha score is very weak",
            "Technical structure is severely weak",
            "Position is below cost basis"
        ]


    elif (
        risk_score < 45
        and market_score < 35
    ):

        action = "EXIT"

        conviction = "HIGH"

        urgency = "HIGH"

        reasons = [
            "Risk profile deteriorated",
            "Technical setup is weak"
        ]


    # ==============================================
    # 2. REDUCE
    # Weak setup but position still has value/profit
    # ==============================================

    elif (
        alpha_score < 45
        and market_score < 35
    ):

        action = "REDUCE"

        conviction = "HIGH"

        urgency = "MEDIUM"

        reasons = [
            "Alpha score is weak",
            "Technical momentum deteriorated"
        ]


        if pnl_pct > 0:

            reasons.append(
                "Protect existing unrealized profit"
            )


    elif (
        sector_score < 20
        and market_score < 40
        and alpha_score < 50
    ):

        action = "REDUCE"

        conviction = "MEDIUM"

        urgency = "MEDIUM"

        reasons = [
            "Sector backdrop is very weak",
            "Technical confirmation is insufficient"
        ]


    # ==============================================
    # 3. ADD
    # Existing position has strong multi-factor support
    # ==============================================

    elif (
        alpha_score >= 65
        and market_score >= 55
        and catalyst_score >= 55
        and sector_score >= 45
        and risk_score >= 60
        and signal == "BULLISH"
    ):

        action = "ADD"

        conviction = "HIGH"

        urgency = "MEDIUM"

        reasons = [
            "Strong alpha profile",
            "Bullish technical confirmation",
            "Catalyst support present",
            "Sector backdrop supportive",
            "Risk profile acceptable"
        ]


    # ==============================================
    # 4. HOLD
    # Thesis still healthy but no reason to add
    # ==============================================

    elif (
        alpha_score >= 55
        and market_score >= 40
        and risk_score >= 55
    ):

        action = "HOLD"

        conviction = "MEDIUM"

        urgency = "LOW"

        reasons = [
            "Position remains fundamentally acceptable",
            "Risk profile remains manageable"
        ]


        if catalyst_score < 55:

            reasons.append(
                "Catalyst confirmation not strong enough to add"
            )


        if sector_score < 45:

            reasons.append(
                "Sector backdrop limits conviction"
            )


    # ==============================================
    # 5. WATCH
    # Mixed evidence
    # ==============================================

    else:

        action = "WATCH"

        conviction = "LOW"

        urgency = "LOW"

        reasons = [
            "Signals are mixed",
            "No immediate portfolio action required"
        ]


    # ==============================================
    # POSITION CONTEXT
    # ==============================================

    if pnl_pct >= 30:

        position_state = (
            "LARGE_UNREALIZED_GAIN"
        )

    elif pnl_pct >= 10:

        position_state = (
            "PROFIT"
        )

    elif pnl_pct > -5:

        position_state = (
            "NEAR_COST"
        )

    elif pnl_pct > -15:

        position_state = (
            "MODERATE_LOSS"
        )

    else:

        position_state = (
            "LARGE_LOSS"
        )


    return {

        "ticker":
        ticker,

        "action":
        action,

        "conviction":
        conviction,

        "urgency":
        urgency,

        "position_state":
        position_state,

        "position":
        metrics,

        "reasons":
        reasons,

        "inputs": {

            "alpha_score":
            alpha_score,

            "market_score":
            market_score,

            "catalyst_score":
            catalyst_score,

            "sector_score":
            sector_score,

            "risk_score":
            risk_score,

            "signal":
            signal
        },

        "data_quality":
        "LIVE"
    }
