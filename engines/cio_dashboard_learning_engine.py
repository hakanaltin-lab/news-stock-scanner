"""
V10.9.2 CIO Dashboard Learning Integration Engine

Purpose:
Integrate AI learning outputs into CIO Dashboard.

Functions:
- Learning metrics
- Strategy performance ranking
- Confidence trend
- CIO learning report
"""


from datetime import datetime



def calculate_decision_accuracy(
    successful_decisions,
    total_decisions
):
    """
    Calculates decision accuracy
    """


    if total_decisions == 0:

        return 0



    return round(

        (

            successful_decisions

            /

            total_decisions

        ) * 100,

        2

    )





def calculate_alpha_improvement(
    previous_alpha,
    updated_alpha
):
    """
    Calculates alpha improvement
    """


    return round(

        updated_alpha - previous_alpha,

        2

    )





def determine_learning_status(
    accuracy
):
    """
    Determines learning maturity
    """


    if accuracy >= 85:

        return "ACTIVE"


    elif accuracy >= 60:

        return "DEVELOPING"


    return "NEEDS_REVIEW"





def rank_strategy(
    strategy_scores
):
    """
    Finds best performing strategy
    """


    if not strategy_scores:

        return None



    return max(

        strategy_scores,

        key=strategy_scores.get

    )





def generate_learning_dashboard(
    decision_accuracy,
    previous_alpha,
    updated_alpha,
    strategy_scores,
    best_pattern
):
    """
    Main CIO dashboard learning function
    """


    alpha_improvement = calculate_alpha_improvement(

        previous_alpha,

        updated_alpha

    )


    best_strategy = rank_strategy(

        strategy_scores

    )


    return {


        "engine":

        "V10.9.2 CIO Dashboard Learning Integration Engine",


        "timestamp":

        datetime.utcnow().isoformat(),


        "learning_status":

        determine_learning_status(

            decision_accuracy

        ),


        "decision_accuracy":

        decision_accuracy,


        "alpha_improvement":

        alpha_improvement,


        "best_pattern":

        best_pattern,


        "best_strategy":

        best_strategy,


        "strategy_scores":

        strategy_scores,


        "dashboard_ready":

        True

    }
