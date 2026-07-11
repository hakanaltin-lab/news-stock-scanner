"""
V8.5 Autonomous Portfolio Manager

Purpose:
Manage portfolio level decisions.

Functions:
- Portfolio health analysis
- Capital allocation
- Rebalancing recommendation
- CIO portfolio guidance
"""


from datetime import datetime



MAX_POSITION_WEIGHT = 10

TARGET_CASH = 30



def calculate_portfolio_health(
    positions,
    cash
):
    """
    Evaluates overall portfolio condition
    """


    total_exposure = 0


    largest_position = 0



    for position in positions:


        weight = position.get(
            "weight",
            0
        )


        total_exposure += weight



        if weight > largest_position:

            largest_position = weight



    if largest_position > MAX_POSITION_WEIGHT:

        concentration = "HIGH"


    elif largest_position > 7:

        concentration = "MEDIUM"


    else:

        concentration = "LOW"



    if cash >= TARGET_CASH:

        liquidity = "HEALTHY"

    else:

        liquidity = "LOW"



    return {


        "exposure":

        total_exposure,


        "cash":

        cash,


        "concentration":

        concentration,


        "liquidity":

        liquidity


    }





def recommend_rebalance(
    positions
):
    """
    Creates rebalance recommendations
    """


    actions = []



    for position in positions:


        weight = position.get(
            "weight",
            0
        )


        ticker = position.get(
            "ticker"
        )



        if weight > MAX_POSITION_WEIGHT:


            actions.append(

                {

                "ticker":

                ticker,


                "action":

                "REDUCE",


                "reason":

                "Position exceeds CIO limit"

                }

            )



        else:


            actions.append(

                {

                "ticker":

                ticker,


                "action":

                "HOLD",


                "reason":

                "Within allocation limit"

                }

            )



    return actions





def generate_capital_allocation(
    opportunities
):
    """
    Allocates new capital based on opportunities
    """


    allocation = []



    for opportunity in opportunities:


        score = opportunity.get(
            "cio_score",
            0
        )


        ticker = opportunity.get(
            "ticker"
        )



        if score >= 85:


            weight = 10


        elif score >= 75:


            weight = 5


        else:


            weight = 2



        allocation.append(

            {

            "ticker":

            ticker,


            "recommended_weight":

            weight

            }

        )



    return allocation





def generate_portfolio_cio_view(
    health,
    rebalance,
    allocation
):
    """
    Creates final portfolio recommendation
    """


    if health["concentration"] == "HIGH":


        action = (

            "REDUCE CONCENTRATION RISK"

        )


    elif health["liquidity"] == "HEALTHY":


        action = (

            "SELECTIVELY INCREASE EXPOSURE"

        )


    else:


        action = (

            "MAINTAIN LIQUIDITY"

        )



    return {


        "engine":

        "V8.5 Autonomous Portfolio Manager",


        "timestamp":

        datetime.utcnow().isoformat(),


        "portfolio_action":

        action,


        "portfolio_health":

        health,


        "rebalance_plan":

        rebalance,


        "capital_allocation":

        allocation

    }
