"""
AURORA AI CIO v3.1

L5.5 Capital Allocation Engine

L5.5.1 Capital Priority Engine v1.0

Purpose:
Rank investment opportunities
based on capital allocation priority.

Inputs:
- Alpha Score
- Conviction
- Expected Return
- Risk
- Catalyst Timing

Output:
Capital Priority Ranking
"""


from datetime import datetime



class CapitalPriorityEngine:


    def __init__(self):

        self.status = "ACTIVE"





    def evaluate_conviction(
        self,
        conviction
    ):

        mapping = {


            "HIGH":

            3,


            "MEDIUM":

            2,


            "LOW":

            1

        }


        return mapping.get(

            conviction,

            0

        )





    def evaluate_risk(
        self,
        risk
    ):

        mapping = {


            "LOW":

            3,


            "MEDIUM":

            2,


            "HIGH":

            1,


            "CRITICAL":

            0

        }


        return mapping.get(

            risk,

            0

        )





    def evaluate_catalyst(
        self,
        catalyst
    ):

        mapping = {


            "IMMEDIATE":

            3,


            "NEAR_TERM":

            2,


            "LONG_TERM":

            1,


            "NONE":

            0

        }


        return mapping.get(

            catalyst,

            0

        )





    def calculate_priority_score(
        self,
        alpha_score,
        conviction_score,
        return_score,
        risk_score,
        catalyst_score
    ):


        return (

            alpha_score

            +

            conviction_score

            +

            return_score

            +

            risk_score

            +

            catalyst_score

        )





    def classify_priority(
        self,
        score
    ):


        if score >= 20:

            return "FIRST_PRIORITY"



        elif score >= 14:

            return "HIGH_PRIORITY"



        elif score >= 8:

            return "MEDIUM_PRIORITY"



        return "LOW_PRIORITY"





    def rank_opportunity(
        self,
        alpha_score,
        conviction,
        expected_return,
        risk,
        catalyst
    ):


        conviction_score = self.evaluate_conviction(

            conviction

        )


        risk_score = self.evaluate_risk(

            risk

        )


        catalyst_score = self.evaluate_catalyst(

            catalyst

        )


        priority_score = self.calculate_priority_score(

            alpha_score,

            conviction_score,

            expected_return,

            risk_score,

            catalyst_score

        )


        priority = self.classify_priority(

            priority_score

        )


        return {


            "engine":

            "L5.5.1 Capital Priority Engine v1.0",


            "timestamp":

            datetime.utcnow().isoformat(),


            "capital_priority_score":

            priority_score,


            "priority":

            priority

        }
