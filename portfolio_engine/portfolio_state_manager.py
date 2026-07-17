"""
AURORA AI CIO v3.1

V4.0 Integration Layer

V4.4 Portfolio State Manager v1.0

Purpose:
Manage live portfolio state.

Tracks:
- Positions
- Cost Basis
- Current Value
- P&L
- Exposure

Output:
Portfolio Health State
"""


from datetime import datetime



class PortfolioStateManager:


    def __init__(self):

        self.status = "ACTIVE"

        self.positions = {}





    def add_position(
        self,
        symbol,
        quantity,
        average_cost
    ):


        self.positions[symbol] = {


            "quantity":

            quantity,


            "average_cost":

            average_cost,


            "current_price":

            average_cost,


            "status":

            "OPEN"

        }


        return self.positions[symbol]





    def update_price(
        self,
        symbol,
        current_price
    ):


        if symbol in self.positions:


            self.positions[symbol]["current_price"] = current_price


            return self.positions[symbol]


        return None





    def calculate_position_value(
        self,
        symbol
    ):


        if symbol not in self.positions:

            return None


        position = self.positions[symbol]


        return (

            position["quantity"]

            *

            position["current_price"]

        )





    def calculate_pnl(
        self,
        symbol
    ):


        if symbol not in self.positions:

            return None


        position = self.positions[symbol]


        return (

            position["current_price"]

            -

            position["average_cost"]

        ) * position["quantity"]





    def calculate_total_exposure(
        self
    ):


        total_value = 0


        for symbol in self.positions:


            total_value += self.calculate_position_value(

                symbol

            )


        return total_value





    def get_portfolio_state(
        self
    ):


        return {


            "engine":

            "V4.4 Portfolio State Manager v1.0",


            "timestamp":

            datetime.utcnow().isoformat(),


            "total_positions":

            len(self.positions),


            "total_exposure":

            self.calculate_total_exposure(),


            "positions":

            self.positions

        }
