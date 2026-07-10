"""
V5.5 Alpha Intelligence Engine

Institutional decision layer

Combines:
- Price Action
- News Catalyst
- Sector Momentum
- Risk
"""


def calculate_alpha_score(
    market_score,
    catalyst_score,
    sector_score,
    risk_score
):

    score = 0

    score += market_score * 0.40
    score += catalyst_score * 0.25
    score += sector_score * 0.20
    score += risk_score * 0.15

    return round(score, 2)



def generate_rating(score):

    if score >= 85:
        return "HIGH CONVICTION"

    elif score >= 70:
        return "ACCUMULATE"

    elif score >= 55:
        return "WATCH"

    elif score >= 40:
        return "HOLD"

    else:
        return "AVOID"



def generate_action(score):

    if score >= 85:
        return "BUY"

    elif score >= 70:
        return "ADD"

    elif score >= 55:
        return "MONITOR"

    else:
        return "NO TRADE"
