"""
AURORA AI CIO v3.1

L5 Portfolio Engine

L5.2 Portfolio Construction Engine v1.0

Purpose:
Construct optimized portfolio allocation.

Inputs:
- Positions
- Sector Weights
- Risk Concentration
- Diversification

Output:
Portfolio Quality Rating
"""


from datetime import datetime



class PortfolioConstructionEngine:


    def __init__(self):

        self.status = "ACTIVE"





    def evaluate_diversification(
        self,
        number_of_positions
    ):

        if number_of_positions >= 15:

            return 2


        elif number_of_positions >= 8:

            return 1


        elif number_of_positions < 5:

            return -1


        return 0





    def evaluate_sector_balance(
        self,
        highest_sector_weight
    ):


        if highest_sector_weight <= 20:

            return 2


        elif highest_sector_weight <= 35:

            return 1


        elif highest_sector_weight > 50:

            return -2


        return 0





    def evaluate_concentration(
        self,
        largest_position_weight
    ):


        if largest_position_weight <= 10:

            return 2


        elif largest_position_weight <= 20:

            return 1


        elif largest_position_weight > 30:

            return -2


        return 0





    def calculate_portfolio_score(
        self,
        diversification,
        sector_balance,
        concentration
    ):

        return (

            diversification

            +

            sector_balance

            +

            concentration

        )





    def classify_portfolio(
        self,
        score
    ):


        if score >= 5:

            return "OPTIMIZED"



        elif score >= 2:

            return "BALANCED"



        elif score >= 0:

            return "CONCENTRATED"



        return "HIGH_RISK"





    def build_portfolio(
        self,
        number_of_positions,
        highest_sector_weight,
        largest_position_weight
    ):


        diversification_score = self.evaluate_diversification(

            number_of_positions

        )


        sector_score = self.evaluate_sector_balance(

            highest_sector_weight

        )


        concentration_score = self.evaluate_concentration(

            largest_position_weight

        )


        total_score = self.calculate_portfolio_score(

            diversification_score,

            sector_score,

            concentration_score

        )


        rating = self.classify_portfolio(

            total_score

        )


        return {


            "engine":

            "L5.2 Portfolio Construction Engine v1.0",


            "timestamp":

            datetime.utcnow().isoformat(),


            "portfolio_score":

            total_score,


            "portfolio_rating":

            rating,


            "inputs":

            {

                "number_of_positions":

                number_of_positions,


                "highest_sector_weight":

                highest_sector_weight,


                "largest_position_weight":

                largest_position_weight

            }

        }
