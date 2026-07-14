"""
V10.6.1 Portfolio Risk Budget Fusion Engine

Purpose:
Evaluate portfolio level risk before
capital allocation decisions.

Functions:
- Sector concentration analysis
- Position risk contribution
- Cash buffer assessment
- Portfolio risk scoring
- Allocation approval
"""


from datetime import datetime



MAX_SECTOR_EXPOSURE = 40

MIN_CASH_BUFFER = 10





def analyze_sector_exposure(
    sector_exposure
):
    """
    Checks sector concentration risk
    """


    if sector_exposure > MAX_SECTOR_EXPOSURE:

        return {

            "status": "HIGH_CONCENTRATION",

            "score": 40

        }



    return {

        "status": "HEALTHY",

        "score": 85

    }





def calculate_position_risk_contribution(
    weight,
    volatility
):
    """
    Calculates position risk contribution
    """


    volatility_multiplier = {


        "LOW": 0.8,

        "MEDIUM": 1.0,

        "HIGH": 1.5

    }



    multiplier = volatility_multiplier.get(

        volatility,

        1.0

    )



    return round(

        weight * multiplier,

        2

    )





def analyze_cash_buffer(
    cash_percentage
):
    """
    Evaluates liquidity protection
    """


    if cash_percentage >= MIN_CASH_BUFFER:

        return {

            "status": "HEALTHY",

            "score": 90

        }



    return {

        "status": "LOW_CASH",

        "score": 50

    }





def calculate_portfolio_risk_score(
    sector_score,
    cash_score,
    diversification_score
):
    """
    Creates overall portfolio risk score
    """


    score = (

        sector_score * 0.4

        +

        cash_score * 0.3

        +

        diversification_score * 0.3

    )


    return round(score)





def determine_risk_action(
    risk_score
):
    """
    Creates risk decision
    """


    if risk_score >= 75:

        return "ALLOW_ALLOCATION"



    elif risk_score >= 50:

        return "LIMIT_ALLOCATION"



    return "BLOCK_ALLOCATION"





def evaluate_portfolio_risk(
    portfolio_name,
    sector_exposure,
    cash_percentage,
    diversification_score
):
    """
    Main portfolio risk function
    """


    sector_result = analyze_sector_exposure(

        sector_exposure

    )


    cash_result = analyze_cash_buffer(

        cash_percentage

    )


    risk_score = calculate_portfolio_risk_score(

        sector_result["score"],

        cash_result["score"],

        diversification_score

    )



    return {


        "engine":

        "V10.6.1 Portfolio Risk Budget Fusion Engine",


        "timestamp":

        datetime.utcnow().isoformat(),


        "portfolio":

        portfolio_name,


        "sector_exposure":

        sector_result,


        "cash_buffer":

        cash_result,


        "portfolio_risk_score":

        risk_score,


        "risk_action":

        determine_risk_action(

            risk_score

        )

    } 
