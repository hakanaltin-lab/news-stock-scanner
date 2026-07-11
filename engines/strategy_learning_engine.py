"""
V7.8 Strategy Learning Engine

Purpose:
Learning layer for AI trading system.

Functions:
- Strategy memory
- Decision feedback
- Pattern recognition
- Rule improvement
- Learning score
"""


from datetime import datetime



def calculate_strategy_score(
    trades
):
    """
    Calculates strategy success score
    """

    if not trades:

        return 0



    wins = 0


    for trade in trades:

        if trade.get(
            "return",
            0
        ) > 0:

            wins += 1



    score = (

        wins

        /

        len(trades)

    ) * 100



    return round(
        score,
        2
    )




def analyze_pattern(
    trades
):
    """
    Identifies successful patterns
    """


    positive = []


    negative = []



    for trade in trades:


        if trade.get(
            "return",
            0
        ) > 0:

            positive.append(
                trade
            )

        else:

            negative.append(
                trade
            )



    return {


        "successful_patterns":

        len(positive),



        "failed_patterns":

        len(negative)

    }





def generate_learning_feedback(
    strategy_name,
    trades
):
    """
    Creates AI learning feedback
    """


    score = calculate_strategy_score(
        trades
    )


    patterns = analyze_pattern(
        trades
    )



    if score >= 70:

        recommendation = (

            "Increase strategy confidence"

        )


    elif score >= 50:

        recommendation = (

            "Keep strategy with tighter risk"

        )


    else:

        recommendation = (

            "Reduce strategy allocation"

        )



    return {


        "engine":

        "V7.8 Strategy Learning Engine",



        "timestamp":

        datetime.utcnow().isoformat(),



        "strategy":

        strategy_name,



        "learning_score":

        score,



        "patterns":

        patterns,



        "recommendation":

        recommendation

    }





def update_strategy_memory(
    memory,
    feedback
):
    """
    Updates AI strategy memory
    """


    memory.append(

        feedback

    )


    return memory
