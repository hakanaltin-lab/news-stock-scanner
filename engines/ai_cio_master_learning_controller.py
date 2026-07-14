"""
V10.9.3 AI CIO Master Learning Controller

Purpose:
Central controller for AI CIO learning system.

Functions:
- Aggregate learning signals
- Generate learning score
- Update strategy mode
- Adjust confidence behavior
"""


from datetime import datetime



def calculate_learning_score(
    decision_accuracy,
    pattern_success_rate,
    alpha_improvement
):
    """
    Calculates overall learning performance score
    """


    score = (

        decision_accuracy * 0.5

        +

        pattern_success_rate * 0.4

        +

        min(alpha_improvement * 2, 10) * 0.1

    )


    return round(

        max(

            0,

            min(

                100,

                score

            )

        )

    )





def determine_strategy_mode(
    learning_score
):
    """
    Determines CIO operating mode
    """


    if learning_score >= 85:

        return "HIGH_CONVICTION"



    elif learning_score >= 60:

        return "NORMAL_MODE"



    return "DEFENSIVE_MODE"





def calculate_confidence_adjustment(
    learning_score
):
    """
    Adjusts CIO confidence
    """


    if learning_score >= 85:

        return 8



    elif learning_score >= 60:

        return 3



    return -5





def determine_future_action(
    strategy_mode
):
    """
    Creates future investment behavior
    """


    if strategy_mode == "HIGH_CONVICTION":

        return "INCREASE_EXPOSURE"



    elif strategy_mode == "NORMAL_MODE":

        return "MAINTAIN_STRATEGY"



    return "REDUCE_RISK"





def generate_learning_control_report(
    decision_accuracy,
    pattern_success_rate,
    alpha_improvement
):
    """
    Main AI CIO learning controller
    """


    learning_score = calculate_learning_score(

        decision_accuracy,

        pattern_success_rate,

        alpha_improvement

    )


    strategy_mode = determine_strategy_mode(

        learning_score

    )


    confidence_adjustment = calculate_confidence_adjustment(

        learning_score

    )


    return {


        "engine":

        "V10.9.3 AI CIO Master Learning Controller",


        "timestamp":

        datetime.utcnow().isoformat(),


        "learning_score":

        learning_score,


        "strategy_mode":

        strategy_mode,


        "confidence_adjustment":

        confidence_adjustment,


        "future_action":

        determine_future_action(

            strategy_mode

        )

    }
