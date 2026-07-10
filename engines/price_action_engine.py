"""
V3 Price Action Engine

Measures stock price behavior before ranking opportunities.
"""

from dataclasses import dataclass


@dataclass
class PriceActionScore:
    ticker: str
    momentum: float
    trend: float
    volume: float
    breakout: float
    final_score: float


def calculate_price_action_score(
    momentum: float,
    trend: float,
    volume: float,
    breakout: float
) -> float:

    return (
        momentum * 0.30 +
        trend * 0.30 +
        volume * 0.20 +
        breakout * 0.20
    )


def analyze_price_action(
    ticker: str,
    momentum: float,
    trend: float,
    volume: float,
    breakout: float
):

    score = calculate_price_action_score(
        momentum,
        trend,
        volume,
        breakout
    )

    return PriceActionScore(
        ticker,
        momentum,
        trend,
        volume,
        breakout,
        score
    )
