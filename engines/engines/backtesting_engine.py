"""
V7.7 Backtesting Engine

Purpose:
Test AI trading decisions against historical outcomes.

Functions:
- Historical trade simulation
- Strategy evaluation
- Win rate calculation
- Drawdown analysis
- Performance summary
"""


from datetime import datetime



def simulate_trade(
    entry_price,
    exit_price
):
    """
    Calculates trade return
    """

    if entry_price == 0:

        return 0


    return round(

        (
            (exit_price - entry_price)
            /
            entry_price

        ) * 100,

        2

    )




def evaluate_trades(
    trades
):
    """
    Evaluates historical trades
    """


    if not trades:

        return {

            "trades":0,
            "win_rate":0,
            "average_return":0

        }



    returns = []


    winners = 0



    for trade in trades:


        result = simulate_trade(

            trade.get(
                "entry",
                0
            ),

            trade.get(
                "exit",
                0
            )

        )


        returns.append(result)



        if result > 0:

            winners += 1




    average_return = (

        sum(returns)

        /

        len(returns)

    )



    win_rate = (

        winners

        /

        len(returns)

    ) * 100



    return {


        "trades":

        len(trades),



        "winning_trades":

        winners,



        "win_rate":

        round(
            win_rate,
            2
        ),



        "average_return":

        round(
            average_return,
            2
        )

    }





def calculate_drawdown(
    equity_curve
):
    """
    Calculates maximum portfolio drawdown
    """


    if not equity_curve:

        return 0



    peak = equity_curve[0]

    max_drawdown = 0



    for value in equity_curve:


        if value > peak:

            peak = value



        drawdown = (

            (value - peak)

            /

            peak

        ) * 100



        if drawdown < max_drawdown:

            max_drawdown = drawdown



    return round(
        max_drawdown,
        2
    )





def run_backtest(
    strategy_name,
    trades,
    equity_curve
):
    """
    Generates complete backtest report
    """


    performance = evaluate_trades(
        trades
    )


    drawdown = calculate_drawdown(
        equity_curve
    )



    return {


        "engine":

        "V7.7 Backtesting Engine",



        "timestamp":

        datetime.utcnow().isoformat(),



        "strategy":

        strategy_name,



        "performance":

        performance,



        "max_drawdown":

        drawdown

    }
