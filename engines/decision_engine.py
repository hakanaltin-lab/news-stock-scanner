"""
V6.5 Institutional Decision Engine

Purpose:
- Convert intelligence scores into actionable decisions
- Require confirmation across Alpha, Market, Catalyst and Risk
- Prevent weak setups from becoming BUY / ACCUMULATE
- Generate entry, stop, target and risk/reward

Decision hierarchy:
BUY
ACCUMULATE
WATCH
AVOID
"""


def calculate_confidence(
    alpha_score,
    market_score,
    catalyst_score,
    risk_score
):

    confidence = (
        alpha_score * 0.50
        + market_score * 0.20
        + catalyst_score * 0.15
        + risk_score * 0.15
    )

    return round(
        max(
            0,
            min(
                100,
                confidence
            )
        ),
        1
    )


def generate_decision(
    alpha_score,
    market_score,
    catalyst_score,
    risk_score,
    price
):

    confidence = calculate_confidence(
        alpha_score,
        market_score,
        catalyst_score,
        risk_score
    )

    decision = {

        "action":
        "AVOID",

        "confidence":
        confidence,

        "entry_zone":
        None,

        "stop_loss":
        None,

        "target_price":
        None,

        "risk_reward":
        None,

        "setup_quality":
        "WEAK",

        "reasons":
        []

    }


    # ==============================================
    # HARD RISK / TECHNICAL FILTERS
    # ==============================================

    if risk_score < 45:

        decision["reasons"].append(
            "Risk profile too weak"
        )

        return decision


    if market_score < 35:

        decision["reasons"].append(
            "Technical setup too weak"
        )

        return decision


    # ==============================================
    # HIGH-CONVICTION BUY
    # ==============================================

    if (
        alpha_score >= 75
        and market_score >= 65
        and catalyst_score >= 60
        and risk_score >= 60
    ):

        decision["action"] = "BUY"

        decision["setup_quality"] = (
            "HIGH_CONVICTION"
        )

        decision["reasons"] = [
            "Strong alpha score",
            "Strong technical confirmation",
            "Positive catalyst confirmation",
            "Acceptable risk profile"
        ]

        decision["entry_zone"] = {

            "low":
            round(
                price * 0.98,
                2
            ),

            "high":
            round(
                price * 1.01,
                2
            )

        }

        decision["stop_loss"] = round(
            price * 0.93,
            2
        )

        decision["target_price"] = round(
            price * 1.18,
            2
        )


    # ==============================================
    # ACCUMULATE
    # ==============================================

    elif (
        alpha_score >= 65
        and market_score >= 55
        and catalyst_score >= 55
        and risk_score >= 55
    ):

        decision["action"] = (
            "ACCUMULATE"
        )

        decision["setup_quality"] = (
            "POSITIVE"
        )

        decision["reasons"] = [
            "Positive alpha score",
            "Technical confirmation present",
            "Catalyst confirmation present",
            "Risk profile acceptable"
        ]

        decision["entry_zone"] = {

            "low":
            round(
                price * 0.96,
                2
            ),

            "high":
            round(
                price,
                2
            )

        }

        decision["stop_loss"] = round(
            price * 0.91,
            2
        )

        decision["target_price"] = round(
            price * 1.15,
            2
        )


    # ==============================================
    # WATCH
    # ==============================================

    elif (
        alpha_score >= 55
        and market_score >= 45
        and risk_score >= 50
    ):

        decision["action"] = "WATCH"

        decision["setup_quality"] = (
            "DEVELOPING"
        )

        decision["reasons"] = [
            "Setup has potential",
            "Further confirmation required"
        ]


    # ==============================================
    # AVOID
    # ==============================================

    else:

        decision["action"] = "AVOID"

        decision["setup_quality"] = "WEAK"

        decision["reasons"] = [
            "Insufficient multi-factor confirmation"
        ]


    # ==============================================
    # RISK / REWARD
    # ==============================================

    if (
        decision["target_price"] is not None
        and decision["stop_loss"] is not None
        and price
    ):

        upside = (
            decision["target_price"]
            - price
        )

        downside = (
            price
            - decision["stop_loss"]
        )

        if downside > 0:

            decision["risk_reward"] = round(
                upside / downside,
                2
            )


    return decision
