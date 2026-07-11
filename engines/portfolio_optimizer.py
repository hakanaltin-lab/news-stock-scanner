"""
V7.5 AI Portfolio Optimizer

Purpose:
AI based portfolio allocation layer.

Functions:
- Position weighting
- Risk adjusted allocation
- Sector exposure control
- Cash recommendation
- CIO portfolio guidance
"""


from datetime import datetime



MAX_POSITION_WEIGHT = 0.10

MAX_SECTOR_WEIGHT = 0.35



def calculate_position_weight(
    alpha_score,
    risk_score
):
    """
    Calculates recommended position size
    """

    if risk_score < 40:

        return 0


    base_weight = (

        alpha_score / 100

    ) * MAX_POSITION_WEIGHT



    risk_adjustment = (

        risk_score / 100

    )


    weight = (

        base_weight *
        risk_adjustment

    )


    return round(
        weight * 100,
        2
    )




def evaluate_asset(
    ticker,
    sector,
    alpha_score,
    risk_score
):
    """
    Evaluates individual portfolio asset
    """


    weight = calculate_position_weight(

        alpha_score,

        risk_score

    )



    return {


        "ticker":
        ticker,


        "sector":
        sector,


        "recommended_weight":

        weight,


        "status":

        "APPROVED"
        if weight > 0
        else
        "REJECTED"

    }





def optimize_portfolio(
    assets
):
    """
    Creates portfolio allocation plan
    """


    allocations = []


    total_allocation = 0



    for asset in assets:


        result = evaluate_asset(

            asset.get("ticker"),

            asset.get(
                "sector",
                "UNKNOWN"
            ),

            asset.get(
                "alpha_score",
                0
            ),

            asset.get(
                "risk_score",
                0
            )

        )


        allocations.append(result)


        total_allocation += result[
            "recommended_weight"
        ]



    cash_position = max(

        0,

        100 - total_allocation

    )



    return {


        "engine":

        "V7.5 Portfolio Optimizer",



        "timestamp":

        datetime.utcnow().isoformat(),



        "allocations":

        allocations,



        "recommended_cash":

        round(
            cash_position,
            2
        ),



        "portfolio_risk":

        "HIGH"
        if total_allocation > 80
        else
        "CONTROLLED"

    }





def generate_cio_portfolio_view(
    optimization
):
    """
    Creates CIO level portfolio recommendation
    """


    if optimization.get(
        "recommended_cash",
        0
    ) > 40:


        recommendation = (

            "Maintain liquidity "
            "and wait for opportunities"

        )


    else:


        recommendation = (

            "Portfolio can increase "
            "selective exposure"

        )



    return {


        "timestamp":

        datetime.utcnow().isoformat(),


        "recommendation":

        recommendation,


        "cash":

        optimization.get(
            "recommended_cash"
        )

    }
