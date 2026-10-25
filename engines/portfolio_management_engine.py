"""
V7.9 AURORA Multi-Horizon Portfolio Management Engine

Purpose:
- Manage positions already owned using strategic 3M-12M daily evidence
- Prevent 15-minute noise from directly causing REDUCE / EXIT decisions
- Use tactical intraday intelligence only for ADD timing
- Preserve cost-basis context and explicit portfolio actions

Actions:
ADD
HOLD
WATCH
REDUCE
EXIT

Design:
- Strategic layer decides whether the long-horizon thesis is healthy.
- Tactical layer decides whether now is a good moment to add.
- Tactical weakness alone cannot trigger REDUCE or EXIT.
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
        *
        avg_cost
    )

    current_value = (
        shares
        *
        current_price
    )

    unrealized_pnl = (
        current_value
        -
        cost_basis
    )

    if cost_basis > 0:
        unrealized_pnl_pct = (
            unrealized_pnl
            /
            cost_basis
            *
            100
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


def classify_position_state(
    pnl_pct
):
    if pnl_pct >= 30:
        return "LARGE_UNREALIZED_GAIN"

    if pnl_pct >= 10:
        return "PROFIT"

    if pnl_pct > -5:
        return "NEAR_COST"

    if pnl_pct > -15:
        return "MODERATE_LOSS"

    return "LARGE_LOSS"


def calculate_strategic_composite(
    strategic_trend_score,
    strategic_risk_score,
    catalyst_score,
    sector_score
):
    score = (
        safe_float(
            strategic_trend_score,
            50
        )
        *
        0.55
        +
        safe_float(
            strategic_risk_score,
            50
        )
        *
        0.20
        +
        safe_float(
            sector_score,
            50
        )
        *
        0.15
        +
        safe_float(
            catalyst_score,
            50
        )
        *
        0.10
    )

    return round(
        min(
            100,
            max(
                0,
                score
            )
        ),
        1
    )


def tactical_add_status(
    tactical_decision,
    tactical_signal
):
    tactical_decision = (
        tactical_decision
        or
        {}
    )

    action = tactical_decision.get(
        "action",
        "AVOID"
    )

    if action in [
        "BUY",
        "ACCUMULATE"
    ]:
        return "ADD_NOW"

    if action == "WATCH":
        return "WAIT_FOR_CONFIRMATION"

    if tactical_signal == "BEARISH":
        return "DO_NOT_ADD_NOW"

    return "WAIT"


def evaluate_portfolio_position(
    ticker,
    shares,
    avg_cost,
    current_price,
    strategic_result,
    catalyst_score,
    sector_score,
    tactical_decision=None,
    tactical_signal=None
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

    strategic_result = (
        strategic_result
        or
        {}
    )

    strategic_metrics = (
        strategic_result.get(
            "metrics",
            {}
        )
        or
        {}
    )

    trend_score = safe_float(
        strategic_result.get(
            "strategic_trend_score",
            50
        ),
        50
    )

    strategic_risk_score = safe_float(
        strategic_result.get(
            "strategic_risk_score",
            50
        ),
        50
    )

    strategic_signal = (
        strategic_result.get(
            "strategic_signal"
        )
        or
        "UNKNOWN"
    )

    return_3m = safe_float(
        strategic_metrics.get(
            "return_3m_pct"
        ),
        0
    )

    return_6m = safe_float(
        strategic_metrics.get(
            "return_6m_pct"
        ),
        0
    )

    rs_3m = safe_float(
        strategic_metrics.get(
            "relative_strength_3m_pct"
        ),
        0
    )

    rs_6m = safe_float(
        strategic_metrics.get(
            "relative_strength_6m_pct"
        ),
        0
    )

    above_sma50 = strategic_metrics.get(
        "above_sma50"
    )

    above_sma100 = strategic_metrics.get(
        "above_sma100"
    )

    above_sma200 = strategic_metrics.get(
        "above_sma200"
    )

    strategic_composite = (
        calculate_strategic_composite(
            strategic_trend_score=trend_score,
            strategic_risk_score=strategic_risk_score,
            catalyst_score=catalyst_score,
            sector_score=sector_score
        )
    )

    tactical_status = tactical_add_status(
        tactical_decision,
        tactical_signal
    )

    action = "WATCH"

    conviction = "LOW"

    urgency = "LOW"

    reasons = []

    # =====================================================
    # 1. EXIT — sustained strategic deterioration only
    # =====================================================

    severe_trend_break = (
        trend_score < 30
        and
        above_sma200 is False
        and
        return_6m <= -20
        and
        rs_6m <= -15
    )

    severe_risk_break = (
        strategic_risk_score < 35
        and
        above_sma200 is False
        and
        return_6m < 0
    )

    if (
        (
            severe_trend_break
            or
            severe_risk_break
        )
        and
        pnl_pct < 0
    ):
        action = "EXIT"

        conviction = "HIGH"

        urgency = "HIGH"

        reasons = [
            "Long-horizon trend has materially deteriorated",
            "Price is below the 200-day trend",
            "Six-month relative strength is weak",
            "Position is below cost basis"
        ]

    # =====================================================
    # 2. REDUCE — strategic weakness, not intraday weakness
    # =====================================================

    elif (
        trend_score < 40
        and
        above_sma200 is False
        and
        return_6m < -8
        and
        rs_6m < -8
    ):
        action = "REDUCE"

        conviction = "HIGH"

        urgency = "MEDIUM"

        reasons = [
            "Strategic trend score is weak",
            "Price is below the 200-day trend",
            "Six-month momentum and relative strength are negative"
        ]

        if pnl_pct > 0:
            reasons.append(
                "Reduce concentration while preserving part of the existing gain"
            )

    elif (
        strategic_composite < 45
        and
        above_sma200 is False
        and
        sector_score < 25
        and
        rs_6m < -5
    ):
        action = "REDUCE"

        conviction = "MEDIUM"

        urgency = "LOW"

        reasons = [
            "Strategic composite is weak",
            "Sector backdrop is weak",
            "Long-horizon relative strength is negative"
        ]

    # =====================================================
    # 3. ADD — strategic thesis strong + tactical timing
    # =====================================================

    elif (
        strategic_composite >= 68
        and
        trend_score >= 65
        and
        strategic_risk_score >= 55
        and
        above_sma200 is True
        and
        return_6m > 0
        and
        rs_6m > 0
        and
        sector_score >= 40
        and
        catalyst_score >= 50
    ):
        if tactical_status == "ADD_NOW":
            action = "ADD"

            conviction = "HIGH"

            urgency = "MEDIUM"

            reasons = [
                "Strategic trend is healthy",
                "Six-month momentum is positive",
                "Relative strength versus SPY is positive",
                "Long-horizon risk profile is acceptable",
                "Tactical timing confirms an add"
            ]

        else:
            action = "HOLD"

            conviction = "HIGH"

            urgency = "LOW"

            reasons = [
                "Strategic thesis supports adding",
                "Long-horizon trend remains healthy",
                "Tactical timing is not attractive enough to add now"
            ]

    # =====================================================
    # 4. HOLD — strategic thesis intact
    # =====================================================

    elif (
        strategic_composite >= 50
        and
        strategic_risk_score >= 45
        and
        (
            above_sma200 is True
            or
            return_6m > 0
            or
            rs_6m > 0
        )
    ):
        action = "HOLD"

        conviction = (
            "HIGH"
            if strategic_composite >= 62
            else
            "MEDIUM"
        )

        urgency = "LOW"

        reasons = [
            "Long-horizon thesis remains intact",
            "No strategic deterioration requiring a reduction"
        ]

        if tactical_status in [
            "DO_NOT_ADD_NOW",
            "WAIT_FOR_CONFIRMATION",
            "WAIT"
        ]:
            reasons.append(
                "Short-term weakness affects timing only; do not add now"
            )

    # =====================================================
    # 5. WATCH — mixed strategic evidence
    # =====================================================

    else:
        action = "WATCH"

        conviction = "LOW"

        urgency = "LOW"

        reasons = [
            "Strategic evidence is mixed",
            "No immediate portfolio action required"
        ]

        if tactical_status == "DO_NOT_ADD_NOW":
            reasons.append(
                "Intraday setup is weak; wait before adding"
            )

    return {
        "ticker":
        ticker,

        "engine":
        "V7.9 Multi-Horizon Portfolio Management Engine",

        "action":
        action,

        "conviction":
        conviction,

        "urgency":
        urgency,

        "position_state":
        classify_position_state(
            pnl_pct
        ),

        "position":
        metrics,

        "strategic_composite_score":
        strategic_composite,

        "strategic_signal":
        strategic_signal,

        "tactical_add_status":
        tactical_status,

        "reasons":
        reasons,

        "strategic_inputs": {
            "strategic_trend_score":
            trend_score,

            "strategic_risk_score":
            strategic_risk_score,

            "return_3m_pct":
            round(
                return_3m,
                2
            ),

            "return_6m_pct":
            round(
                return_6m,
                2
            ),

            "relative_strength_3m_pct":
            round(
                rs_3m,
                2
            ),

            "relative_strength_6m_pct":
            round(
                rs_6m,
                2
            ),

            "above_sma50":
            above_sma50,

            "above_sma100":
            above_sma100,

            "above_sma200":
            above_sma200,

            "sector_score":
            sector_score,

            "catalyst_score":
            catalyst_score
        },

        "tactical_inputs": {
            "signal":
            tactical_signal,

            "entry_action":
            (
                (
                    tactical_decision
                    or
                    {}
                ).get(
                    "action"
                )
            ),

            "confidence":
            (
                (
                    tactical_decision
                    or
                    {}
                ).get(
                    "confidence"
                )
            )
        },

        "data_quality":
        strategic_result.get(
            "data_quality",
            "UNKNOWN"
        )
    }
