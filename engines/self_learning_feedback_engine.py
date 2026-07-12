"""
V9.4 Self-Learning Feedback Loop Engine

Purpose:
Create continuous learning from trading outcomes.

Functions:
- Trade outcome analysis
- Error detection
- Strategy learning score
- Parameter improvement feedback
"""


from datetime import datetime



def evaluate_trade_result(
    entry_price,
    exit_price
):
    """
    Calculates trade performance
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





def classify_trade(
    return_pct
):
    """
    Classifies trade outcome
    """


    if return_pct >= 10:

        return "SUCCESS"


    elif return_pct > 0:

        return "POSITIVE"



    elif return_pct <= -10:

        return "FAILURE"



    return "NEGATIVE"





def calculate_learning_score(
    trades
):
    """
    Measures strategy learning performance
    """


    if not trades:

        return 0



    successful = 0



    for trade in trades:


        if trade.get(
            "result",
            ""
        ) in [

            "SUCCESS",

            "POSITIVE"

        ]:

            successful += 1



    score = (

        successful

        /

        len(trades)

    ) * 100



    return round(score)





def generate_feedback(
    strategy_name,
    trades
):
    """
    Generates learning feedback
    """


    learning_score = calculate_learning_score(
        trades
    )


    if learning_score >= 75:

        recommendation = (

            "INCREASE_STRATEGY_CONFIDENCE"

        )



    elif learning_score >= 50:

        recommendation = (

            "MAINTAIN_CURRENT_PARAMETERS"

        )



    else:

        recommendation = (

            "REDUCE_STRATEGY_WEIGHT"

        )



    return {


        "engine":

        "V9.4 Self Learning Feedback Engine",


        "timestamp":

        datetime.utcnow().isoformat(),


        "strategy":

        strategy_name,


        "learning_score":

        learning_score,


        "recommendation":

        recommendation

    }





def analyze_trade_history(
    trades
):
    """
    Converts trade history into learning data
    """


    results = []



    for trade in trades:


        performance = evaluate_trade_result(

            trade.get(
                "entry_price",
                0
            ),

            trade.get(
                "exit_price",
                0
            )

        )


        results.append(

            {

            "ticker":

            trade.get(
                "ticker"
            ),


            "return":

            performance,


            "result":

            classify_trade(
                performance
            )

            }

        )


    return results
