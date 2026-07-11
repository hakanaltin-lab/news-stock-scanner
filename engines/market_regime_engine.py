"""
V8.6 Market Regime Intelligence Engine

Purpose:
Determine current market environment
for autonomous CIO decision making.

Functions:
- Market trend analysis
- Volatility assessment
- Breadth evaluation
- Risk appetite detection
- CIO exposure recommendation
"""


from datetime import datetime



def calculate_trend_score(
    sp500_trend,
    nasdaq_trend
):
    """
    Evaluate index trend strength
    """

    score = (

        sp500_trend * 0.5

        +

        nasdaq_trend * 0.5

    )

    return round(score)




def calculate_volatility_score(
    vix_level
):
    """
    Evaluate volatility environment
    """


    if vix_level < 15:

        return 90


    elif vix_level < 20:

        return 75


    elif vix_level < 30:

        return 50


    else:

        return 25





def determine_regime(
    trend_score,
    volatility_score,
    breadth_score
):
    """
    Generate market regime
    """


    total_score = round(

        trend_score * 0.45

        +

        volatility_score * 0.30

        +

        breadth_score * 0.25

    )



    if total_score >= 80:

        regime = "BULLISH"

        action = "INCREASE_EQUITY_EXPOSURE"



    elif total_score >= 60:

        regime = "NEUTRAL"

        action = "SELECTIVE_BUYING"



    elif total_score >= 40:

        regime = "CAUTION"

        action = "REDUCE_NEW_POSITIONS"



    else:

        regime = "RISK_OFF"

        action = "RAISE_CASH"



    return {


        "market_regime":

        regime,


        "confidence":

        total_score,


        "cio_action":

        action

    }





def analyze_market_environment(
    sp500_trend,
    nasdaq_trend,
    vix_level,
    breadth_score
):
    """
    Main V8.6 Market Intelligence Function
    """


    trend_score = calculate_trend_score(

        sp500_trend,

        nasdaq_trend

    )



    volatility_score = calculate_volatility_score(

        vix_level

    )



    regime = determine_regime(

        trend_score,

        volatility_score,

        breadth_score

    )



    return {


        "engine":

        "V8.6 Market Regime Intelligence Engine",


        "timestamp":

        datetime.utcnow().isoformat(),


        "market_metrics":

        {


            "trend_score":

            trend_score,


            "volatility_score":

            volatility_score,


            "breadth_score":

            breadth_score

        },


        "cio_decision":

        regime

    }
