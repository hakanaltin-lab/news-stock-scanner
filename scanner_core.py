"""
V4 Market Intelligence Scanner Core

Scoring engine
"""



class MarketScanner:


    def __init__(self):

        self.version = "V4"



    def calculate_score(
        self,
        news_score,
        sector_score,
        price_score,
        quality_score,
        risk_score
    ):

        score = (

            news_score * 0.25 +

            sector_score * 0.20 +

            price_score * 0.20 +

            quality_score * 0.25 +

            (100 - risk_score) * 0.10

        )

        return round(score, 2)



    def get_action(self, score):

        if score >= 85:

            return "STRONG BUY / ACCUMULATE"


        elif score >= 70:

            return "HOLD / ADD ON PULLBACK"


        elif score >= 55:

            return "WATCH"


        else:

            return "AVOID"



    def scan_stock(
        self,
        ticker,
        news_score,
        sector_score,
        price_score,
        quality_score,
        risk_score
    ):


        score = self.calculate_score(

            news_score,
            sector_score,
            price_score,
            quality_score,
            risk_score

        )


        return {

            "ticker": ticker,

            "score": score,

            "action": self.get_action(score),

            "news": news_score,

            "sector": sector_score,

            "quality": quality_score,

            "risk": risk_score

        }
