"""
AURORA AI CIO v3.1

L6 Independent Risk Authority

Drawdown Circuit Breaker v1.0

Purpose:
Protect portfolio capital during
excessive losses.

Controls:
- Daily drawdown
- Weekly drawdown
- Maximum drawdown
- Automatic risk actions
"""


from datetime import datetime



def calculate_drawdown(
    peak_value,
    current_value
):
    """
    Calculates portfolio drawdown percentage.
    """


    if peak_value <= 0:

        return 0


    drawdown = (

        (peak_value - current_value)

        /

        peak_value

    ) * 100


    return round(

        drawdown,

        2

    )





def evaluate_drawdown_level(
    drawdown_percentage
):
    """
    Determines circuit breaker level.
    """


    if drawdown_percentage >= 15:

        return "EMERGENCY_HALT"



    elif drawdown_percentage >= 10:

        return "FREEZE_NEW_POSITIONS"



    elif drawdown_percentage >= 5:

        return "REDUCE_EXPOSURE"



    elif drawdown_percentage >= 3:

        return "WARNING"



    return "NORMAL"





def determine_action(
    drawdown_level
):
    """
    Converts risk level into action.
    """


    actions = {


        "NORMAL":

        "CONTINUE",


        "WARNING":

        "MONITOR_CLOSELY",


        "REDUCE_EXPOSURE":

        "LOWER_POSITION_SIZE",


        "FREEZE_NEW_POSITIONS":

        "BLOCK_NEW_TRADES",


        "EMERGENCY_HALT":

        "STOP_ALL_EXECUTION"

    }


    return actions.get(

        drawdown_level,

        "REVIEW"

    )





def run_drawdown_check(
    peak_value,
    current_value
):
    """
    Main circuit breaker function.
    """


    drawdown = calculate_drawdown(

        peak_value,

        current_value

    )


    level = evaluate_drawdown_level(

        drawdown

    )


    action = determine_action(

        level

    )


    return {


        "engine":

        "L6.6 Drawdown Circuit Breaker v1.0",


        "timestamp":

        datetime.utcnow().isoformat(),


        "peak_value":

        peak_value,


        "current_value":

        current_value,


        "drawdown_percentage":

        drawdown,


        "circuit_level":

        level,


        "action":

        action

    }
