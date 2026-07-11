"""
V8.7 Dynamic Asset Allocation Engine

Purpose:
Allocate capital dynamically based on
market regime and risk environment.

Functions:
- Regime based allocation
- Risk adjustment
- CIO portfolio targets
"""


from datetime import datetime



def get_base_allocation(
    market_regime
):
    """
    Creates allocation based on market regime
    """


    if market_regime == "BULLISH":

        return {

            "equity_target": 85,

            "growth_target": 45,

            "defensive_target": 10,

            "cash_target": 15

        }



    elif market_regime == "NEUTRAL":

        return {

            "equity_target": 65,

            "growth_target": 30,

            "defensive_target": 20,

            "cash_target": 35

        }



    elif market_regime == "CAUTION":

        return {

            "equity_target": 50,

            "growth_target": 20,

            "defensive_target": 25,

            "cash_target": 50

        }



    else:

        return {

            "equity_target": 35,

            "growth_target": 10,

            "defensive_target": 35,

            "cash_target": 40

        }





def adjust_for_risk(
    allocation,
    risk_level
):
    """
    Adjust exposure according to risk
    """


    if risk_level == "HIGH":

        allocation["equity_target"] -= 15

        allocation["cash_target"] += 15



    elif risk_level == "LOW":

        allocation["equity_target"] += 5

        allocation["cash_target"] -= 5



    return allocation





def generate_cio_allocation(
    market_regime,
    risk_level
):
    """
    Main CIO allocation function
    """


    allocation = get_base_allocation(

        market_regime

    )


    allocation = adjust_for_risk(

        allocation,

        risk_level

    )



    if allocation["equity_target"] >= 75:

        action = "INCREASE_RISK_EXPOSURE"



    elif allocation["equity_target"] >= 50:

        action = "MAINTAIN_BALANCED_EXPOSURE"



    else:

        action = "PROTECT_CAPITAL"




    return {


        "engine":

        "V8.7 Dynamic Asset Allocation Engine",


        "timestamp":

        datetime.utcnow().isoformat(),


        "market_regime":

        market_regime,


        "risk_level":

        risk_level,


        "allocation":

        allocation,


        "cio_action":

        action

    }
