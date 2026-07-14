"""
AURORA AI CIO v3.1

L6 Independent Risk Authority

Position Limit Engine v1.0

Purpose:
Control maximum position exposure
before portfolio approval.

This module acts as a CRO-level
risk control, independent from
portfolio construction.
"""


from datetime import datetime



def calculate_position_limit(
    risk_level,
    conviction_score,
    market_regime
):
    """
    Determines maximum allowed position size.

    risk_level:
    LOW / MEDIUM / HIGH

    conviction_score:
    0-100

    market_regime:
    BULL / NORMAL / BEAR
    """

    base_limit = 5


    # Risk adjustment

    if risk_level == "LOW":
        base_limit = 15

    elif risk_level == "MEDIUM":
        base_limit = 10

    elif risk_level == "HIGH":
        base_limit = 5



    # Conviction adjustment

    if conviction_score >= 90:
        base_limit += 3

    elif conviction_score >= 75:
        base_limit += 1



    # Market regime adjustment

    if market_regime == "BEAR":
        base_limit -= 3

    elif market_regime == "BULL":
        base_limit += 2



    return max(
        2,
        min(
            20,
            base_limit
        )
    )





def evaluate_position_request(
    ticker,
    requested_position,
    risk_level,
    conviction_score,
    market_regime
):
    """
    Main CRO position approval logic.
    """


    allowed_limit = calculate_position_limit(

        risk_level,

        conviction_score,

        market_regime

    )


    if requested_position <= allowed_limit:

        decision = "APPROVE"


    elif requested_position <= allowed_limit + 3:

        decision = "REDUCE"


    else:

        decision = "BLOCK"



    return {

        "engine":

        "L6 Position Limit Engine v1.0",


        "timestamp":

        datetime.utcnow().isoformat(),


        "ticker":

        ticker,


        "requested_position":

        requested_position,


        "allowed_limit":

        allowed_limit,


        "risk_level":

        risk_level,


        "conviction_score":

        conviction_score,


        "market_regime":

        market_regime,


        "decision":

        decision

    }
