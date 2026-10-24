"""
V6.5 Calibrated Alpha Intelligence Engine

Purpose:
- Combine normalized intelligence scores
- Prevent sector score from dominating the model
- Give more importance to risk quality
- Produce a balanced 0-100 alpha score

Weights:
Market Technicals : 35%
Catalyst           : 25%
Sector             : 15%
Risk Quality       : 25%
"""


def clamp(
    value,
    minimum=0,
    maximum=100
):

    return max(
        minimum,
        min(
            maximum,
            value
        )
    )


def calculate_alpha_score(
    market_score,
    catalyst_score,
    sector_score,
    risk_score
):

    score = (

        market_score * 0.35

        + catalyst_score * 0.25

        + sector_score * 0.15

        + risk_score * 0.25

    )

    return round(
        clamp(
            score
        ),
        2
    )


def generate_rating(score):

    if score >= 80:
        return "EXCEPTIONAL"

    elif score >= 70:
        return "STRONG"

    elif score >= 60:
        return "POSITIVE"

    elif score >= 50:
        return "NEUTRAL"

    elif score >= 40:
        return "CAUTIOUS"

    else:
        return "WEAK"


def generate_action(score):

    """
    Legacy compatibility only.

    Final investment action is generated
    by decision_engine.py.
    """

    if score >= 75:
        return "DECISION ENGINE REVIEW"

    elif score >= 60:
        return "WATCHLIST"

    else:
        return "NO TRADE"
