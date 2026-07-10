"""
V3 Risk Engine

Purpose:
Evaluate downside risk before portfolio selection.
"""

from dataclasses import dataclass


@dataclass
class RiskScore:
    ticker: str
    volatility: float
    drawdown: float
    valuation_risk: float
    liquidity_risk: float
    final_score: float


def calculate_risk_score(
    ticker: str,
    volatility: float,
    drawdown: float,
    valuation_risk: float,
    liquidity_risk: float,
) -> RiskScore:

    risk = (
        volatility * 0.30
        + drawdown * 0.30
        + valuation_risk * 0.25
        + liquidity_risk * 0.15
    )

    final_score = max(0, 100 - risk)

    return RiskScore(
        ticker=ticker,
        volatility=volatility,
        drawdown=drawdown,
        valuation_risk=valuation_risk,
        liquidity_risk=liquidity_risk,
        final_score=final_score,
    )
