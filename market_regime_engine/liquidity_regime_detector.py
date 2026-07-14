"""
AURORA AI CIO v3.1

L1 Market Regime Engine

Liquidity Regime Detector v1.0

Purpose:
Detect market liquidity conditions.

Outputs:
- LIQUIDITY_EXPANDING
- LIQUIDITY_NEUTRAL
- LIQUIDITY_TIGHTENING
"""


from datetime import datetime



class LiquidityRegimeDetector:


    def __init__(self):

        self.status = "ACTIVE"





    def evaluate_rates(
        self,
        interest_rate_change
    ):
        """
        Evaluates interest rate pressure.
        """


        if interest_rate_change < 0:

            return 1


        elif interest_rate_change > 0:

            return -1


        return 0





    def evaluate_fed_liquidity(
        self,
        fed_liquidity
    ):
        """
        Evaluates central bank liquidity.
        """


        if fed_liquidity == "EXPANDING":

            return 1



        elif fed_liquidity == "TIGHTENING":

            return -1



        return 0





    def evaluate_credit_conditions(
        self,
        credit_condition
    ):
        """
        Evaluates credit market.
        """


        if credit_condition == "EASY":

            return 1



        elif credit_condition == "TIGHT":

            return -1



        return 0





    def calculate_liquidity_score(
        self,
        rate_score,
        fed_score,
        credit_score
    ):

        return (

            rate_score

            +

            fed_score

            +

            credit_score

        )





    def classify_liquidity(
        self,
        score
    ):
        """
        Final liquidity classification.
        """


        if score >= 2:

            return "LIQUIDITY_EXPANDING"



        elif score <= -2:

            return "LIQUIDITY_TIGHTENING"



        return "LIQUIDITY_NEUTRAL"





    def analyze_liquidity(
        self,
        interest_rate_change,
        fed_liquidity,
        credit_condition
    ):
        """
        Main liquidity engine.
        """


        rate_score = self.evaluate_rates(

            interest_rate_change

        )


        fed_score = self.evaluate_fed_liquidity(

            fed_liquidity

        )


        credit_score = self.evaluate_credit_conditions(

            credit_condition

        )


        total_score = self.calculate_liquidity_score(

            rate_score,

            fed_score,

            credit_score

        )


        regime = self.classify_liquidity(

            total_score

        )


        return {


            "engine":

            "L1.3 Liquidity Regime Detector v1.0",


            "timestamp":

            datetime.utcnow().isoformat(),


            "liquidity_score":

            total_score,


            "liquidity_regime":

            regime,


            "inputs":

            {

                "rate_change":

                interest_rate_change,


                "fed_liquidity":

                fed_liquidity,


                "credit_condition":

                credit_condition

            }

        }
