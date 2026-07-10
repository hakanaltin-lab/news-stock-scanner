"""
V3 Alpha Ranking Engine

Combines:
- Catalyst
- Sector Momentum
- Price Action
- Quality
- Risk
"""


from dataclasses import dataclass


@dataclass
class AlphaScore:
    ticker: str
    catalyst: float
    sector: float
    price_action: float
    technical: float
    quality: float
    risk: float
    final_score: float



def calculate_alpha_score(
    ticker,
    catalyst,
    sector,
    price_action,
    technical,
    quality,
    risk
):

    return (
        catalyst * 0.25 +
        sector * 0.20 +
        price_action * 0.20 +
        technical * 0.15 +
        quality * 0.15 +
        risk * 0.05
    )



def rank_stock(
    ticker,
    catalyst,
    sector,
    price_action,
    technical,
    quality,
    risk
):

    score = calculate_alpha_score(
    ticker,
    catalyst,
    sector,
    price_action,
    technical,
    quality,
    risk
)

    return AlphaScore(
        ticker,
        catalyst,
        sector,
        price_action,
        technical,
        quality,
        risk,
        score
    )
