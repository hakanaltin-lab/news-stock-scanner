"""
V7.6 Performance Attribution Engine

Purpose:
Analyze portfolio performance and identify
sources of returns and risks.

Functions:
- Return attribution
- Strategy performance
- Sector contribution
- Risk analysis
- CIO performance review
"""


from datetime import datetime



def calculate_return(
    entry_value,
    current_value
):
    """
    Calculates investment return percentage
    """

    if entry_value == 0:

        return 0


    return round(

        (
            (current_value - entry_value)
            /
            entry_value

        ) * 100,

        2

    )




def analyze_trade_performance(
    trades
):
    """
    Calculates trade statistics
    """

    if not trades:

        return {

            "total_trades":0,

            "winning_trades":0,

            "losing_trades":0,

            "win_rate":0

        }



    winners = []

    losers = []



    for trade in trades:


        if trade.get(
            "return",
            0
        ) > 0:

            winners.append(trade)

        else:

            losers.append(trade)



    win_rate = (

        len(winners)
        /
        len(trades)

    ) * 100



    return {


        "total_trades":

        len(trades),


        "winning_trades":

        len(winners),


        "losing_trades":

        len(losers),


        "win_rate":

        round(
            win_rate,
            2
        )

    }





def calculate_sector_attribution(
    positions
):
    """
    Calculates sector contribution
    """


    sectors = {}



    for position in positions:


        sector = position.get(
            "sector",
            "UNKNOWN"
        )


        contribution = position.get(
            "return",
            0
        )


        if sector not in sectors:

            sectors[sector] = 0



        sectors[sector] += contribution



    return sectors





def calculate_strategy_attribution(
    strategies
):
    """
    Measures strategy contribution
    """


    result = {}



    for strategy in strategies:


        name = strategy.get(
            "strategy",
            "UNKNOWN"
        )


        performance = strategy.get(
            "return",
            0
        )


        result[name] = performance



    return result





def generate_cio_performance_review(
    portfolio_return,
    sector_results,
    strategy_results
):
    """
    Creates CIO performance report
    """


    if portfolio_return > 0:

        assessment = (
            "Portfolio generating positive alpha"
        )

    else:

        assessment = (
            "Portfolio requires optimization"
        )



    return {


        "engine":

        "V7.6 Performance Attribution Engine",



        "timestamp":

        datetime.utcnow().isoformat(),



        "portfolio_return":

        portfolio_return,



        "assessment":

        assessment,



        "sector_contribution":

        sector_results,



        "strategy_contribution":

        strategy_results

    }
