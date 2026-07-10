"""
V5.4 Scoring Engine

Institutional style stock scoring layer

Inputs:
- Market snapshot
- Momentum
- VWAP
- Volume

Output:
- Score
- Rating
- Confidence
"""


def calculate_market_score(snapshot):

    score = 0

    price = snapshot.get(
        "last_price",
        0
    )

    vwap = snapshot.get(
        "vwap",
        0
    )

    momentum = snapshot.get(
        "momentum",
        0
    )

    volume = snapshot.get(
        "volume",
        0
    )


    # VWAP condition
    if price > vwap:
        score += 15
    else:
        score += 5


    # Momentum
    if momentum > 2:
        score += 15
    elif momentum > 0:
        score += 10


    # Volume
    if volume > 500000:
        score += 10
    elif volume > 100000:
        score += 5


    return score



def calculate_catalyst_score():

    # Future connection:
    # News engine
    # Earnings
    # Analyst upgrades

    return 20



def calculate_risk_score(snapshot):

    # Future:
    # volatility
    # drawdown
    # liquidity risk

    return 10



def generate_stock_score(snapshot):

    market = calculate_market_score(snapshot)

    catalyst = calculate_catalyst_score()

    risk = calculate_risk_score(snapshot)


    total = (
        market +
        catalyst +
        risk
    )


    if total >= 85:
        rating = "STRONG BUY"

    elif total >= 70:
        rating = "BUY"

    elif total >= 55:
        rating = "WATCH"

    elif total >= 40:
        rating = "HOLD"

    else:
        rating = "AVOID"


    confidence = "MEDIUM"


    return {

        "score": total,

        "rating": rating,

        "confidence": confidence,

        "breakdown": {

            "market": market,

            "catalyst": catalyst,

            "risk": risk

        }

    }
