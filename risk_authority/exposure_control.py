"""
AURORA AI CIO v3.1

L6 Independent Risk Authority

Exposure Control Engine v1.0

Purpose:
Control portfolio level exposure risk.

Controls:
- Sector concentration
- Total market exposure
- Portfolio concentration
"""


from datetime import datetime



def check_sector_exposure(
    sector,
    sector_weight,
    maximum_sector_limit
):
    """
    Controls sector concentration.
    """


    if sector_weight <= maximum_sector_limit:

        return "APPROVE"


    elif sector_weight <= maximum_sector_limit + 5:

        return "WARNING"


    return "REDUCE"





def check_total_exposure(
    equity_exposure,
    market_regime
):
    """
    Controls total portfolio market exposure.
    """


    if market_regime == "BEAR":

        if equity_exposure > 70:

            return "REDUCE"



    elif market_regime == "BULL":

        if equity_exposure <= 100:

            return "APPROVE"



    if equity_exposure > 100:

        return "BLOCK"



    return "APPROVE"





def check_concentration_risk(
    top_three_weight
):
    """
    Controls portfolio concentration.
    """


    if top_three_weight <= 45:

        return "APPROVE"


    elif top_three_weight <= 60:

        return "WARNING"


    return "HIGH_RISK"





def evaluate_portfolio_exposure(
    sector,
    sector_weight,
    maximum_sector_limit,
    equity_exposure,
    market_regime,
    top_three_weight
):
    """
    Main exposure control engine.
    """


    sector_status = check_sector_exposure(

        sector,

        sector_weight,

        maximum_sector_limit

    )


    exposure_status = check_total_exposure(

        equity_exposure,

        market_regime

    )


    concentration_status = check_concentration_risk(

        top_three_weight

    )


    decision = "APPROVE"



    if "REDUCE" in [
        sector_status,
        exposure_status
    ]:

        decision = "REDUCE"



    if "BLOCK" in [
        exposure_status
    ]:

        decision = "BLOCK"



    if concentration_status == "HIGH_RISK":

        decision = "WARNING"



    return {


        "engine":

        "L6 Exposure Control Engine v1.0",


        "timestamp":

        datetime.utcnow().isoformat(),


        "sector":

        sector,


        "sector_status":

        sector_status,


        "total_exposure_status":

        exposure_status,


        "concentration_status":

        concentration_status,


        "final_decision":

        decision

    }
