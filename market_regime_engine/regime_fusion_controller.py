"""
AURORA AI CIO v3.1

L1 Market Regime Engine

Regime Fusion Controller v1.0

Purpose:
Combine all market regime signals.

Inputs:
- Direction
- Volatility
- Liquidity
- Momentum
- Risk Appetite

Output:
Master Market Regime
"""


from datetime import datetime



class RegimeFusionController:


    def __init__(self):

        self.status = "ACTIVE"





    def score_direction(
        self,
        direction
    ):

        mapping = {


            "BULLISH":

            2,


            "BEARISH":

            -2,


            "NEUTRAL":

            0

        }


        return mapping.get(

            direction,

            0

        )





    def score_volatility(
        self,
        volatility
    ):

        mapping = {


            "LOW_VOLATILITY":

            1,


            "NORMAL_VOLATILITY":

            0,


            "HIGH_VOLATILITY":

            -1,


            "VOLATILITY_SPIKE":

            -2

        }


        return mapping.get(

            volatility,

            0

        )





    def score_liquidity(
        self,
        liquidity
    ):

        mapping = {


            "LIQUIDITY_EXPANDING":

            1,


            "LIQUIDITY_NEUTRAL":

            0,


            "LIQUIDITY_TIGHTENING":

            -1

        }


        return mapping.get(

            liquidity,

            0

        )





    def score_momentum(
        self,
        momentum
    ):

        mapping = {


            "STRONG_MOMENTUM":

            2,


            "NORMAL_MOMENTUM":

            1,


            "WEAK_MOMENTUM":

            0,


            "NEGATIVE_MOMENTUM":

            -2

        }


        return mapping.get(

            momentum,

            0

        )





    def score_risk_appetite(
        self,
        appetite
    ):

        mapping = {


            "RISK_SEEKING":

            2,


            "NEUTRAL":

            0,


            "RISK_AVERSION":

            -1,


            "PANIC":

            -2

        }


        return mapping.get(

            appetite,

            0

        )





    def classify_master_regime(
        self,
        score
    ):

        if score >= 6:

            return "AGGRESSIVE_RISK_ON"



        elif score >= 3:

            return "RISK_ON"



        elif score <= -6:

            return "CRISIS_MODE"



        elif score <= -3:

            return "DEFENSIVE"



        return "NEUTRAL"





    def analyze_regime(
        self,
        direction,
        volatility,
        liquidity,
        momentum,
        risk_appetite
    ):
        """
        Main fusion engine.
        """


        total_score = (

            self.score_direction(direction)

            +

            self.score_volatility(volatility)

            +

            self.score_liquidity(liquidity)

            +

            self.score_momentum(momentum)

            +

            self.score_risk_appetite(risk_appetite)

        )


        master_regime = self.classify_master_regime(

            total_score

        )


        return {


            "engine":

            "L1.6 Regime Fusion Controller v1.0",


            "timestamp":

            datetime.utcnow().isoformat(),


            "regime_score":

            total_score,


            "master_market_regime":

            master_regime,


            "inputs":

            {

                "direction":

                direction,


                "volatility":

                volatility,


                "liquidity":

                liquidity,


                "momentum":

                momentum,


                "risk_appetite":

                risk_appetite

            }

        }
