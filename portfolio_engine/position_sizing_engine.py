"""
AURORA AI CIO v3.1

L5 Portfolio Engine

L5.1 Position Sizing Engine v1.0

Purpose:
Calculate optimal position size.

Inputs:
- Conviction Score
- Risk Score
- Volatility
- Stop Loss Distance
- Portfolio Exposure

Output:
Recommended Position Size
"""


from datetime import datetime



class PositionSizingEngine:


    def __init__(self):

        self.status = "ACTIVE"





    def conviction_multiplier(
        self,
        conviction
    ):

        mapping = {

            "HIGH": 1.5,

            "MEDIUM": 1.0,

            "LOW": 0.5

        }


        return mapping.get(

            conviction,

            0.5

        )





    def risk_multiplier(
        self,
        risk_level
    ):

        mapping = {

            "LOW": 1.2,

            "MEDIUM": 1.0,

            "HIGH": 0.6,

            "CRITICAL": 0.3

        }


        return mapping.get(

            risk_level,

            0.5

        )





    def volatility_multiplier(
        self,
        volatility
    ):

        mapping = {

            "LOW": 1.2,

            "NORMAL": 1.0,

            "HIGH": 0.7

        }


        return mapping.get(

            volatility,

            1.0

        )





    def calculate_base_position(
        self,
        portfolio_value,
        max_allocation
    ):


        return (

            portfolio_value

            *

            max_allocation

        )





    def calculate_position_size(
        self,
        portfolio_value,
        max_allocation,
        conviction,
        risk_level,
        volatility
    ):


        base_position = self.calculate_base_position(

            portfolio_value,

            max_allocation

        )


        final_position = (

            base_position

            *

            self.conviction_multiplier(

                conviction

            )

            *

            self.risk_multiplier(

                risk_level

            )

            *

            self.volatility_multiplier(

                volatility

            )

        )


        return final_position





    def classify_position(
        self,
        position_percentage
    ):


        if position_percentage >= 10:

            return "CORE_POSITION"



        elif position_percentage >= 5:

            return "STANDARD_POSITION"



        elif position_percentage >= 2:

            return "SMALL_POSITION"



        return "WATCH_POSITION"





    def build_position(
        self,
        portfolio_value,
        max_allocation,
        conviction,
        risk_level,
        volatility
    ):


        position_value = self.calculate_position_size(

            portfolio_value,

            max_allocation,

            conviction,

            risk_level,

            volatility

        )


        position_percentage = (

            position_value

            /

            portfolio_value

        ) * 100


        return {


            "engine":

            "L5.1 Position Sizing Engine v1.0",


            "timestamp":

            datetime.utcnow().isoformat(),


            "position_value":

            position_value,


            "position_percentage":

            position_percentage,


            "position_type":

            self.classify_position(

                position_percentage

            )

        }
