"""
AURORA AI CIO v3.1

L5.5 Capital Allocation Engine

L5.5.2 Allocation Optimizer v1.0

Purpose:
Optimize capital distribution
across investment opportunities.

Inputs:
- Total Capital
- Opportunity Scores
- Risk Levels
- Allocation Limits

Output:
Optimized Capital Allocation
"""


from datetime import datetime



class AllocationOptimizer:


    def __init__(self):

        self.status = "ACTIVE"





    def risk_adjustment(
        self,
        risk_level
    ):

        mapping = {


            "LOW":

            1.2,


            "MEDIUM":

            1.0,


            "HIGH":

            0.7,


            "CRITICAL":

            0.3

        }


        return mapping.get(

            risk_level,

            0.5

        )





    def calculate_weight(
        self,
        priority_score,
        risk_level
    ):


        adjusted_score = (

            priority_score

            *

            self.risk_adjustment(

                risk_level

            )

        )


        return adjusted_score





    def normalize_weights(
        self,
        weights
    ):


        total = sum(weights.values())


        if total == 0:

            return weights



        normalized = {}



        for asset, weight in weights.items():


            normalized[asset] = (

                weight

                /

                total

            ) * 100



        return normalized





    def apply_position_limit(
        self,
        allocations,
        max_position
    ):


        adjusted = {}



        for asset, weight in allocations.items():


            if weight > max_position:

                adjusted[asset] = max_position


            else:

                adjusted[asset] = weight



        return adjusted





    def allocate_capital(
        self,
        total_capital,
        opportunities,
        max_position
    ):


        raw_weights = {}



        for opportunity in opportunities:


            asset = opportunity["symbol"]


            score = opportunity["priority_score"]


            risk = opportunity["risk"]



            raw_weights[asset] = self.calculate_weight(

                score,

                risk

            )



        normalized = self.normalize_weights(

            raw_weights

        )


        final_weights = self.apply_position_limit(

            normalized,

            max_position

        )


        allocations = {}



        for asset, percentage in final_weights.items():


            allocations[asset] = (

                total_capital

                *

                percentage

                /

                100

            )



        return {


            "engine":

            "L5.5.2 Allocation Optimizer v1.0",


            "timestamp":

            datetime.utcnow().isoformat(),


            "allocation_percentage":

            final_weights,


            "capital_allocation":

            allocations

        }
