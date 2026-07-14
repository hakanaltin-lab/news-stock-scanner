"""
V10.8.2 Trade Lifecycle Manager

Purpose:
Manage complete trade lifecycle from
execution to performance feedback.

Functions:
- Order tracking
- Position monitoring
- P/L calculation
- Exit management
- Trade feedback
"""


from datetime import datetime



VALID_STATES = [

    "CREATED",

    "VALIDATED",

    "SUBMITTED",

    "FILLED",

    "CLOSED"

]





def update_order_status(
    order,
    new_status
):
    """
    Updates order lifecycle state
    """


    if new_status in VALID_STATES:

        order["status"] = new_status



    order["updated_at"] = datetime.utcnow().isoformat()


    return order





def create_position(
    ticker,
    quantity,
    entry_price
):
    """
    Creates open position record
    """


    return {


        "ticker":

        ticker,


        "quantity":

        quantity,


        "entry_price":

        entry_price,


        "status":

        "OPEN",


        "created_at":

        datetime.utcnow().isoformat()

    }





def calculate_position_return(
    entry_price,
    current_price
):
    """
    Calculates unrealized return
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





def evaluate_exit_signal(
    return_percent,
    thesis_status,
    stop_loss,
    take_profit
):
    """
    Determines exit action
    """


    if thesis_status == "BROKEN":

        return "EXIT"



    if return_percent <= stop_loss:

        return "STOP_LOSS"



    if return_percent >= take_profit:

        return "TAKE_PROFIT"



    return "HOLD"





def generate_trade_feedback(
    ticker,
    return_percent
):
    """
    Creates learning feedback
    """


    if return_percent > 0:

        result = "PROFIT"

        learning = "POSITIVE"



    elif return_percent < 0:

        result = "LOSS"

        learning = "REVIEW"



    else:

        result = "BREAKEVEN"

        learning = "NEUTRAL"



    return {


        "ticker":

        ticker,


        "trade_result":

        result,


        "return_percent":

        return_percent,


        "learning_signal":

        learning

    }





def close_trade(
    position,
    exit_price
):
    """
    Closes trade and calculates result
    """


    return_percent = calculate_position_return(

        position["entry_price"],

        exit_price

    )


    position["exit_price"] = exit_price

    position["return_percent"] = return_percent

    position["status"] = "CLOSED"

    position["closed_at"] = datetime.utcnow().isoformat()



    return {


        "position":

        position,


        "feedback":

        generate_trade_feedback(

            position["ticker"],

            return_percent

        )

    }
