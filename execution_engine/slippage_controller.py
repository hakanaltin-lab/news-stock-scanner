"""
AURORA AI CIO v3.1

L7 Execution Engine

L7.4 Slippage Controller v1.0

Purpose:
Measure execution efficiency.

Inputs:
- Expected Price
- Executed Price
- Order Size
- Market Impact

Output:
Execution Quality Rating
"""


from datetime import datetime



class SlippageController:


    def __init__(self):

        self.status = "ACTIVE"





    def calculate_slippage(
        self,
        expected_price,
        executed_price
    ):


        if expected_price == 0:

            return 0


        return (

            (

                executed_price

                -

                expected_price

            )

            /

            expected_price

        ) * 100





    def evaluate_slippage_level(
        self,
        slippage
    ):


        if abs(slippage) <= 0.10:

            return "EXCELLENT_EXECUTION"



        elif abs(slippage) <= 0.50:

            return "GOOD_EXECUTION"



        elif abs(slippage) <= 1.00:

            return "ACCEPTABLE"



        return "POOR_EXECUTION"





    def evaluate_market_impact(
        self,
        impact
    ):


        mapping = {


            "LOW":

            2,


            "MEDIUM":

            1,


            "HIGH":

            -1,


            "EXTREME":

            -2

        }


        return mapping.get(

            impact,

            0

        )





    def calculate_execution_score(
        self,
        slippage,
        impact_score
    ):


        score = impact_score


        if abs(slippage) <= 0.10:

            score += 3


        elif abs(slippage) <= 0.50:

            score += 2


        elif abs(slippage) <= 1:

            score += 1


        else:

            score -= 2


        return score





    def analyze_execution(
        self,
        symbol,
        expected_price,
        executed_price,
        market_impact
    ):


        slippage = self.calculate_slippage(

            expected_price,

            executed_price

        )


        impact_score = self.evaluate_market_impact(

            market_impact

        )


        execution_score = self.calculate_execution_score(

            slippage,

            impact_score

        )


        quality = self.evaluate_slippage_level(

            slippage

        )


        return {


            "engine":

            "L7.4 Slippage Controller v1.0",


            "timestamp":

            datetime.utcnow().isoformat(),


            "symbol":

            symbol,


            "slippage_percent":

            slippage,


            "execution_score":

            execution_score,


            "execution_quality":

            quality

        }
