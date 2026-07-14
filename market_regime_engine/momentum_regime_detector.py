"""
AURORA AI CIO v3.1

L1 Market Regime Engine

Momentum Regime Detector v1.0

Purpose:
Detect market momentum strength.

Outputs:
- STRONG_MOMENTUM
- NORMAL_MOMENTUM
- WEAK_MOMENTUM
- NEGATIVE_MOMENTUM
"""


from datetime import datetime



class MomentumRegimeDetector:


    def __init__(self):

        self.status = "ACTIVE"





    def evaluate_trend_strength(
        self,
        trend_strength
    ):
        """
        Evaluates trend strength score.

        Range:
        0-100
        """


        if trend_strength >= 80:

            return 2


        elif trend_strength >= 50:

            return 1


        elif trend_strength < 30:

            return -1


        return 0





    def evaluate_market_breadth(
        self,
        breadth_percentage
    ):
        """
        Evaluates market participation.
        """


        if breadth_percentage >= 70:

            return 2


        elif breadth_percentage >= 50:

            return 1


        elif breadth_percentage < 30:

            return -1


        return 0





    def evaluate_sector_leadership(
        self,
        leadership
    ):
        """
        Evaluates leading sector behavior.
        """


        if leadership == "STRONG":

            return 1


        elif leadership == "WEAK":

            return -1


        return 0





    def calculate_momentum_score(
        self,
        trend_score,
        breadth_score,
        sector_score
    ):

        return (

            trend_score

            +

            breadth_score

            +

            sector_score

        )





    def classify_momentum(
        self,
        score
    ):
        """
        Final momentum classification.
        """


        if score >= 4:

            return "STRONG_MOMENTUM"



        elif score >= 2:

            return "NORMAL_MOMENTUM"



        elif score <= 0:

            return "NEGATIVE_MOMENTUM"



        return "WEAK_MOMENTUM"





    def analyze_momentum(
        self,
        trend_strength,
        breadth_percentage,
        sector_leadership
    ):
        """
        Main momentum engine.
        """


        trend_score = self.evaluate_trend_strength(

            trend_strength

        )


        breadth_score = self.evaluate_market_breadth(

            breadth_percentage

        )


        sector_score = self.evaluate_sector_leadership(

            sector_leadership

        )


        total_score = self.calculate_momentum_score(

            trend_score,

            breadth_score,

            sector_score

        )


        momentum = self.classify_momentum(

            total_score

        )


        return {


            "engine":

            "L1.4 Momentum Regime Detector v1.0",


            "timestamp":

            datetime.utcnow().isoformat(),


            "momentum_score":

            total_score,


            "momentum_regime":

            momentum,


            "inputs":

            {

                "trend_strength":

                trend_strength,


                "market_breadth":

                breadth_percentage,


                "sector_leadership":

                sector_leadership

            }

        }
