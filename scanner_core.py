"""
V3 Market Scanner Core Engine

Combines:
- Catalyst
- Sector Momentum
- Price Action
- Technical Score
- Quality
- Risk
"""

from engines.alpha_engine import calculate_alpha_score


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

        # Temporary technical engine
        # Will be replaced with live indicators later
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


        final_risk = risk_score


        return {
            "ticker": ticker,
            "alpha_score": alpha_score,
            "risk_score": final_risk,
            "technical_score": technical_score
        }


    def rank_market(self, stocks):

        results = []

        for stock in stocks:

            result = self.scan_stock(
                ticker=stock["ticker"],
                news_score=stock.get("news_score", 50),
                sector_score=stock.get("sector_score", 50),
                price_score=stock.get("price_score", 50),
                quality_score=stock.get("quality_score", 50),
                risk_score=stock.get("risk_score", 50)
            )

            results.append(result)


        return sorted(
            results,
            key=lambda x: x["alpha_score"],
            reverse=True
        )
