"""
AURORA AI CIO v3.1

L5.5 Capital Allocation Engine

L5.5.3 Rebalancing Engine v1.0

Purpose:
Determine when portfolio allocation
should be adjusted.

Inputs:
- Current Weight
- Target Weight
- Alpha Change
- Risk Change

Output:
Rebalancing Decision
"""


from datetime import datetime



class RebalancingEngine:


    def __init__(self):

        self.status = "ACTIVE"





    def calculate_weight_deviation(
        self,
        current_weight,
        target_weight
    ):

        return abs(

            current_weight

            -

            target_weight

        )





    def evaluate_alpha_change(
        self,
        alpha_status
    ):

        mapping = {


            "IMPROVING":

            2,


            "STABLE":

            1,


            "WEAKENING":

            -1,


            "FAILED":

            -2

        }


        return mapping.get(

            alpha_status,

            0

        )





    def evaluate_risk_change(
        self,
        risk_status
    ):

        mapping = {


            "LOWER":

            1,


            "STABLE":

            0,


            "HIGHER":

            -1,


            "CRITICAL":

            -2

        }


        return mapping.get(

            risk_status,

            0

        )





    def determine_action(
        self,
        deviation,
        alpha_score,
        risk_score
    ):


        if (

            alpha_score <= -2

            or

            risk_score <= -2

        ):

            return "EXIT"



        elif (

            deviation >= 10

            and

            alpha_score > 0

        ):

            return "INCREASE"



        elif (

            deviation >= 10

            and

            alpha_score < 0

        ):

            return "REDUCE"



        elif deviation >= 5:

            return "REBALANCE"



        return "HOLD"





    def analyze_position(
        self,
        symbol,
        current_weight,
        target_weight,
        alpha_status,
        risk_status
    ):


        deviation = self.calculate_weight_deviation(

            current_weight,

            target_weight

        )


        alpha_score = self.evaluate_alpha_change(

            alpha_status

        )


        risk_score = self.evaluate_risk_change(

            risk_status

        )


        action = self.determine_action(

            deviation,

            alpha_score,

            risk_score

        )


        return {


            "engine":

            "L5.5.3 Rebalancing Engine v1.0",


            "timestamp":

            datetime.utcnow().isoformat(),


            "symbol":

            symbol,


            "current_weight":

            current_weight,


            "target_weight":

            target_weight,


            "deviation":

            deviation,


            "decision":

            action

        }
