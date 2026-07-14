"""
V10.6 Portfolio Construction Engine

Purpose:
Transform investment signals into
portfolio allocation decisions.

Functions:
- Position sizing
- Conviction allocation
- Risk limits
- Portfolio weight recommendation
"""


from datetime import datetime



MAX_POSITION_WEIGHT = 15

MIN_POSITION_WEIGHT = 1





def determine_position_type(
    alpha_score
):
    """
    Classifies position conviction
    """


    if alpha_score >= 90:

        return "CORE"


    elif alpha_score >= 70:

        return "SATELLITE"


    return "WATCHLIST"





def calculate_target_weight(
    alpha_score,
    cio_confidence,
    risk_level
):
    """
    Calculates portfolio allocation weight
    """


    base_weight = 0



    if alpha_score >= 90:

        base_weight = 10


    elif alpha_score >= 80:

        base_weight = 7


    elif alpha_score >= 70:

        base_weight = 4


    else:

        base_weight = 1



    if cio_confidence >= 90:

        base_weight += 3


    elif cio_confidence < 60:

        base_weight -= 2



    if risk_level == "HIGH":

        base_weight -= 3



    return max(

        MIN_POSITION_WEIGHT,

        min(

            MAX_POSITION_WEIGHT,

            base_weight

        )

    )





def check_allocation_risk(
    target_weight
):
    """
    Checks position concentration risk
    """


    if target_weight > MAX_POSITION_WEIGHT:

        return "EXCEEDS_LIMIT"



    return "APPROVED"





def construct_position(
    ticker,
    alpha_score,
    cio_confidence,
    risk_level
):
    """
    Creates portfolio position recommendation
    """


    weight = calculate_target_weight(

        alpha_score,

        cio_confidence,

        risk_level

    )


    return {


        "engine":

        "V10.6 Portfolio Construction Engine",


        "timestamp":

        datetime.utcnow().isoformat(),


        "ticker":

        ticker,


        "alpha_score":

        alpha_score,


        "cio_confidence":

        cio_confidence,


        "risk_level":

        risk_level,


        "target_weight_percent":

        weight,


        "position_type":

        determine_position_type(

            alpha_score

        ),


        "allocation_status":

        check_allocation_risk(

            weight

        )

    }





def build_portfolio(
    positions
):
    """
    Creates portfolio allocation summary
    """


    total_weight = sum(

        position["target_weight_percent"]

        for position in positions

    )


    return {


        "engine":

        "V10.6 Portfolio Construction Engine",


        "positions":

        positions,


        "total_allocated_percent":

        total_weight,


        "portfolio_status":

        "BALANCED"

        if total_weight <= 100

        else

        "OVER_ALLOCATED"

    }
