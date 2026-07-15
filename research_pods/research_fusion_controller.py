"""
AURORA AI CIO v3.1

L2 Research Pods

L2.7 Research Fusion Controller v1.0

Purpose:
Combine all research pod outputs.

Inputs:
- Fundamental Score
- Quant Score
- Macro Score
- Sentiment Score
- Adversarial Risk
- Execution Score

Output:
Investment Conviction Rating
"""


from datetime import datetime



class ResearchFusionController:


    def __init__(self):

        self.status = "ACTIVE"





    def evaluate_adversarial_risk(
        self,
        risk_rating
    ):

        mapping = {


            "LOW_RISK":

            2,


            "MODERATE_RISK":

            0,


            "HIGH_RISK":

            -2,


            "THESIS_FAILURE":

            -4

        }


        return mapping.get(

            risk_rating,

            0

        )





    def normalize_score(
        self,
        score,
        max_score
    ):
        """
        Converts score into percentage.
        """

        if max_score == 0:

            return 0


        return (

            score

            /

            max_score

        ) * 100





    def calculate_conviction(
        self,
        fundamental,
        quant,
        macro,
        sentiment,
        adversarial,
        execution
    ):


        return (

            fundamental

            +

            quant

            +

            macro

            +

            sentiment

            +

            adversarial

            +

            execution

        )





    def classify_conviction(
        self,
        score
    ):


        if score >= 12:

            return "HIGH_CONVICTION"



        elif score >= 6:

            return "MEDIUM_CONVICTION"



        elif score >= 0:

            return "LOW_CONVICTION"



        return "REJECT"





    def analyze_investment(
        self,
        fundamental_score,
        quant_score,
        macro_score,
        sentiment_score,
        adversarial_risk,
        execution_score
    ):


        adversarial_score = self.evaluate_adversarial_risk(

            adversarial_risk

        )


        total_score = self.calculate_conviction(

            fundamental_score,

            quant_score,

            macro_score,

            sentiment_score,

            adversarial_score,

            execution_score

        )


        conviction = self.classify_conviction(

            total_score

        )


        return {


            "engine":

            "L2.7 Research Fusion Controller v1.0",


            "timestamp":

            datetime.utcnow().isoformat(),


            "investment_score":

            total_score,


            "conviction_rating":

            conviction,


            "inputs":

            {

                "fundamental":

                fundamental_score,


                "quant":

                quant_score,


                "macro":

                macro_score,


                "sentiment":

                sentiment_score,


                "adversarial":

                adversarial_risk,


                "execution":

                execution_score

            }

        }
