"""
V3 Market Intelligence Scanner Core

Combines:
- News Catalyst Engine
- Sector Momentum Engine
- Price Action Engine
- Alpha Ranking Engine
- Risk Management Engine
- Portfolio Selection Engine
"""

from engines.alpha_engine import calculate_alpha_score
from engines.risk_engine import calculate_risk_score


class MarketScanner:

    def __init__(self):
        self.version = "V3"

    def scan_stock(
        self,
        ticker,
        news_score,
        sector_score,
        price_score,
        quality_score,
        risk_score
    ):
    technical_score = 50

    alpha_score = calculate_alpha_score(
    ticker=ticker,
    catalyst=news_score,
    sector=sector_score,
    price_action=price_score,
    technical=technical_score,
    quality=quality_score,
    risk=risk_score
)

        final_risk = calculate_risk_score(
            ticker=ticker,
            risk_score=risk_score
        )

        return {
            "ticker": ticker,
            "alpha_score": alpha_score,
            "risk_score": final_risk
        }


    def rank_market(self, stocks):

        results = []

        for stock in stocks:

            result = self.scan_stock(
                ticker=stock["ticker"],
                news_score=stock["news"],
                sector_score=stock["sector"],
                price_score=stock["price"],
                quality_score=stock["quality"],
                risk_score=stock["risk"]
            )

            results.append(result)

        return sorted(
            results,
            key=lambda x: x["alpha_score"],
            reverse=True
        )
