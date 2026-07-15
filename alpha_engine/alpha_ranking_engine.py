"""
AURORA AI CIO v3.1

L3 Alpha Generation Engine

L3.5 Alpha Ranking Engine v1.0

Purpose:
Rank investment opportunities.

Inputs:
- Opportunity Score
- Factor Alpha Score
- Catalyst Score
- Expected Return Score
- Risk Penalty

Output:
Alpha Ranking
"""


from datetime import datetime



class AlphaRankingEngine:


    def __init__(self):

        self.status = "ACTIVE"





    def evaluate_risk_penalty(
        self,
        risk_level
    ):

        mapping = {


            "LOW":

            0,


            "MEDIUM":

            -2,


            "HIGH":

            -5,


            "CRITICAL":

            -8

        }


        return mapping.get(

            risk_level,

            0

        )





    def calculate_final_alpha_score(
        self,
        opportunity,
        factor_alpha,
        catalyst,
        expected_return,
        risk_penalty
    ):

        return (

            opportunity

            +

            factor_alpha

            +

            catalyst

            +

            expected_return

            +

            risk_penalty

        )





    def classify_alpha(
        self,
        score
    ):


        if score >= 20:

            return "TOP_ALPHA"



        elif score >= 14:

            return "HIGH_ALPHA"



        elif score >= 8:

            return "MEDIUM_ALPHA"



        elif score >= 3:

            return "LOW_ALPHA"



        return "REJECT"





    def rank_opportunity(
        self,
        opportunity_score,
        factor_alpha_score,
        catalyst_score,
        expected_return_score,
        risk_level
    ):


        risk_penalty = self.evaluate_risk_penalty(

            risk_level

        )


        final_score = self.calculate_final_alpha_score(

            opportunity_score,

            factor_alpha_score,

            catalyst_score,

            expected_return_score,

            risk_penalty

        )


        ranking = self.classify_alpha(

            final_score

        )


        return {


            "engine":

            "L3.5 Alpha Ranking Engine v1.0",


            "timestamp":

            datetime.utcnow().isoformat(),


            "final_alpha_score":

            final_score,


            "alpha_ranking":

            ranking,


            "risk_level":

            risk_level

        }
