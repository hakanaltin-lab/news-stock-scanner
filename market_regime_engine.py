"""
AURORA AI CIO v3.1

L1 Market Regime Engine v1.0

Purpose:
Identify current market environment.

Outputs:
- RISK_ON
- RISK_OFF
- NEUTRAL
- HIGH_VOLATILITY
"""


from datetime import datetime



class MarketRegimeEngine:


    def __init__(self):

        self.status = "ACTIVE"





    def evaluate_market_trend(
        self,
        market_trend
    ):
        """
        Evaluates market direction.
        """


        if market_trend == "BULLISH":

            return 1


        elif market_trend == "BEARISH":

            return -1


        return 0





    def evaluate_volatility(
        self,
        volatility_level
    ):
        """
        Evaluates volatility regime.
        """


        if volatility_level == "HIGH":

            return -2


        elif volatility_level == "LOW":

            return 1


        return 0





    def evaluate_liquidity(
        self,
        liquidity_condition
    ):
        """
        Evaluates liquidity environment.
        """


        if liquidity_condition == "EASY":

            return 1


        elif liquidity_condition == "TIGHT":

            return -1


        return 0





    def evaluate_macro(
        self,
        macro_environment
    ):
        """
        Evaluates macro regime.
        """


        if macro_environment == "POSITIVE":

            return 1


        elif macro_environment == "NEGATIVE":

            return -1


        return 0





    def calculate_regime_score(
        self,
        trend,
        volatility,
        liquidity,
        macro
    ):

        return (

            trend

            +

            volatility

            +

            liquidity

            +

            macro

        )





    def classify_regime(
        self,
        score,
        volatility_level
    ):
        """
        Final market regime classification.
        """


        if volatility_level == "HIGH":

            return "HIGH_VOLATILITY"



        if score >= 2:

            return "RISK_ON"



        elif score <= -2:

            return "RISK_OFF"



        return "NEUTRAL"





    def analyze_regime(
        self,
        market_trend,
        volatility_level,
        liquidity_condition,
        macro_environment
    ):
        """
        Main regime engine.
        """


        trend_score = self.evaluate_market_trend(

            market_trend

        )


        volatility_score = self.evaluate_volatility(

            volatility_level

        )


        liquidity_score = self.evaluate_liquidity(

            liquidity_condition

        )


        macro_score = self.evaluate_macro(

            macro_environment

        )


        total_score = self.calculate_regime_score(

            trend_score,

            volatility_score,

            liquidity_score,

            macro_score

        )


        regime = self.classify_regime(

            total_score,

            volatility_level

        )


        return {


            "engine":

            "L1 Market Regime Engine v1.0",


            "timestamp":

            datetime.utcnow().isoformat(),


            "regime_score":

            total_score,


            "market_regime":

            regime,


            "inputs":

            {

                "trend":

                market_trend,


                "volatility":

                volatility_level,


                "liquidity":

                liquidity_condition,


                "macro":

                macro_environment

            }

        }
