"""
V6.8 Market Regime Engine

Market environment intelligence layer.

Functions:
- Bull / Bear detection
- Volatility regime
- Risk environment
- Strategy adjustment
"""


from datetime import datetime


BULL_THRESHOLD = 1.05
BEAR_THRESHOLD = 0.95



def detect_market_regime(
    index_price,
    moving_average,
    volatility
):
    """
    Determines current market regime
    """


    if moving_average == 0:

        return {
            "regime": "UNKNOWN",
            "confidence": 0
        }


    trend_ratio = index_price / moving_average


    if trend_ratio >= BULL_THRESHOLD:

        regime = "BULL"


    elif trend_ratio <= BEAR_THRESHOLD:

        regime = "BEAR"


    else:

        regime = "SIDEWAYS"



    if volatility > 0.30:

        volatility_state = "HIGH_VOLATILITY"

    elif volatility > 0.15:

        volatility_state = "NORMAL_VOLATILITY"

    else:

        volatility_state = "LOW_VOLATILITY"



    return {

        "timestamp":
        datetime.utcnow().isoformat(),

        "regime":
        regime,

        "volatility":
        volatility_state,

        "trend_ratio":
        round(trend_ratio,4),

        "confidence":
        calculate_confidence(
            trend_ratio,
            volatility
        )

    }




def calculate_confidence(
    trend_ratio,
    volatility
):
    """
    Calculates regime confidence score
    """


    score = 50


    if trend_ratio > 1.05 or trend_ratio < 0.95:

        score += 25


    if volatility < 0.30:

        score += 15


    return min(score,100)




def strategy_adjustment(
    regime
):
    """
    Adjusts strategy according to market condition
    """


    if regime == "BULL":

        return {

            "risk_multiplier": 1.2,

            "allocation":
            "AGGRESSIVE"

        }


    if regime == "BEAR":

        return {

            "risk_multiplier": 0.5,

            "allocation":
            "DEFENSIVE"

        }



    return {

        "risk_multiplier": 0.8,

        "allocation":
        "BALANCED"

    }




def market_regime_snapshot(
    regime_data
):
    """
    Creates market intelligence snapshot
    """

    return {

        "engine":
        "V6.8",

        "timestamp":
        datetime.utcnow().isoformat(),

        "market_regime":
        regime_data.get(
            "regime"
        ),

        "volatility":
        regime_data.get(
            "volatility"
        )

    }
