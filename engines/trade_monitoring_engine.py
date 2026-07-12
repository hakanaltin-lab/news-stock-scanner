"""
V9.2 Autonomous Trade Monitoring Engine

Purpose:
Monitor open positions after execution.

Functions:
- Position tracking
- Profit/loss analysis
- Dynamic stop management
- Exit intelligence
"""


from datetime import datetime



def calculate_return(
    entry_price,
    current_price
):
    """
    Calculates position return
    """

    if entry_price == 0:

        return 0


    return round(

        (
            (current_price - entry_price)

            /

            entry_price

        ) * 100,

        2

    )





def evaluate_position(
    return_pct,
    stop_loss,
    target_price,
    current_price
):
    """
    Determines position action
    """


    if return_pct <= stop_loss:

        return "EXIT"



    if current_price >= target_price:

        return "TRIM"



    if return_pct >= 10:

        return "MOVE_STOP_HIGHER"



    if return_pct > 0:

        return "HOLD"



    return "WATCH"





def monitor_position(
    ticker,
    entry_price,
    current_price,
    stop_loss=-8,
    target_price=0
):
    """
    Main position monitoring function
    """


    return_pct = calculate_return(

        entry_price,

        current_price

    )



    action = evaluate_position(

        return_pct,

        stop_loss,

        target_price,

        current_price

    )



    return {


        "engine":

        "V9.2 Autonomous Trade Monitoring Engine",


        "timestamp":

        datetime.utcnow().isoformat(),


        "ticker":

        ticker,


        "entry_price":

        entry_price,


        "current_price":

        current_price,


        "return_pct":

        return_pct,


        "action":

        action

    }





def portfolio_monitor(
    positions
):
    """
    Monitors multiple positions
    """


    results = []



    for position in positions:


        result = monitor_position(

            position.get(
                "ticker"
            ),

            position.get(
                "entry_price"
            ),

            position.get(
                "current_price"
            ),

            position.get(
                "stop_loss",
                -8
            ),

            position.get(
                "target_price",
                0
            )

        )


        results.append(
            result
        )



    return results
