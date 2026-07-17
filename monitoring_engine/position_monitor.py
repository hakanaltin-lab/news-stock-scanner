"""
AURORA AI CIO v3.1

L8 Monitoring Engine

L8.1 Position Monitor v1.0

Purpose:
Monitor open portfolio positions.

Tracks:
- Entry Price
- Current Price
- Unrealized P&L
- Return %
- Position Status

Output:
Position Health Report
"""


from datetime import datetime



class PositionMonitor:


    def __init__(self):

        self.status = "ACTIVE"

        self.positions = {}





    def add_position(
        self,
        symbol,
        quantity,
        entry_price
    ):


        self.positions[symbol] = {


            "quantity":

            quantity,


            "entry_price":

            entry_price,


            "status":

            "OPEN"

        }


        return self.positions[symbol]





    def calculate_pnl(
        self,
        symbol,
        current_price
    ):


        if symbol not in self.positions:

            return None


        position = self.positions[symbol]


        pnl = (

            current_price

            -

            position["entry_price"]

        ) * position["quantity"]


        return pnl





    def calculate_return(
        self,
        symbol,
        current_price
    ):


        if symbol not in self.positions:

            return None


        entry_price = self.positions[symbol]["entry_price"]


        if entry_price == 0:

            return 0


        return (

            (

                current_price

                -

                entry_price

            )

            /

            entry_price

        ) * 100





    def evaluate_position_health(
        self,
        return_percentage
    ):


        if return_percentage >= 10:

            return "STRONG"



        elif return_percentage >= 0:

            return "HEALTHY"



        elif return_percentage >= -5:

            return "WATCH"



        return "WARNING"





    def monitor_position(
        self,
        symbol,
        current_price
    ):


        pnl = self.calculate_pnl(

            symbol,

            current_price

        )


        return_percentage = self.calculate_return(

            symbol,

            current_price

        )


        health = self.evaluate_position_health(

            return_percentage

        )


        return {


            "engine":

            "L8.1 Position Monitor v1.0",


            "timestamp":

            datetime.utcnow().isoformat(),


            "symbol":

            symbol,


            "current_price":

            current_price,


            "pnl":

            pnl,


            "return_percentage":

            return_percentage,


            "health":

            health

        }
